import hashlib
import io
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from session_data import ChooseSession, ImportProblem, ReplaySession, load_session, project_history
from server import ReplayServer, old_wire, report_zip
from playback import playback_segment


def event(seq, kind, payload, run="r1"):
    return {"seq":seq, "timestamp":f"2026-10-09T08:00:{seq:02d}Z", "type":kind,
            "run_id":run, "session_id":"test", "payload":payload}


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.session = self.root / "会话 with spaces"
        self.session.mkdir()
        events = [event(1,"run_started",{}),event(2,"user_turn_committed",{"content":"hello"}),
                  event(3,"execution_recorded",{"execution_id":"a", "kind":"reasoning", "react_iter":1,"text_delta":"甲","run_id":"r1"}),
                  event(4,"execution_recorded",{"execution_id":"a", "kind":"reasoning", "react_iter":1,"text_delta":"乙","run_id":"r1"}),
                  event(5,"ui_event",{"type":"llm_reasoning","react_iter":1,"content":"甲乙"}),
                  event(6,"run_finished",{}),event(7,"run_started",{},"r2"),
                  event(8,"user_turn_committed",{"content":"second"},"r2"),
                  event(9,"ui_event",{"type":"llm_reasoning_delta","ephemeral":True,"react_iter":1,"delta":"丙"},"r2"),
                  event(10,"ui_event",{"type":"llm_reasoning","react_iter":1,"content":"丙"},"r2")]
        (self.session / "events.jsonl").write_text("\n".join(json.dumps(e,ensure_ascii=False) for e in events)+"\n",encoding="utf-8")
        (self.session / "metadata.json").write_text('{"name":"test"}',encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_folder_zip_equivalent_and_read_only(self):
        before = (self.session/"events.jsonl").read_bytes()
        archive = self.root / "a.zip"
        with zipfile.ZipFile(archive,"w") as z:
            for p in self.session.iterdir(): z.write(p,"wrapper/"+p.name)
        a,b = load_session(self.session),load_session(archive)
        self.assertEqual(a["journal_sha256"],b["journal_sha256"])
        self.assertEqual(a["events"],b["events"])
        self.assertEqual(before,(self.session/"events.jsonl").read_bytes())

    def test_mixed_native_and_legacy_rounds(self):
        s=ReplaySession(load_session(self.session))
        texts=[u for u in s.units if u["scope"]=="text"]
        self.assertEqual(len(texts),2)
        self.assertNotEqual(texts[0]["run_id"],texts[1]["run_id"])
        for u,text in zip(texts,["甲乙","丙"]):
            seg=s.segment(u["id"])
            self.assertEqual(seg["expected_texts"][0]["text"],text)
            self.assertEqual(seg["packet_count"],2)
        self.assertEqual(s.segment(texts[1]["id"])["packets"][0]["wire"]["type"],"llm_reasoning_delta")
        self.assertEqual(s.segment(texts[0]["id"])["history"][0]["content"],"hello")

    def test_blob_integrity_truncated_tail_and_missing_snapshot(self):
        blob=self.session/"blobs/a.txt";blob.parent.mkdir();blob.write_text("长文本",encoding="utf-8")
        ref={"blob_ref":"blobs/a.txt","sha256":hashlib.sha256(blob.read_bytes()).hexdigest()}
        row=event(1,"user_turn_committed",{"content_ref":ref})
        (self.session/"events.jsonl").write_text(json.dumps(row)+'\n{"seq":',encoding="utf-8")
        snapshots=self.session/"snapshots";snapshots.mkdir()
        (snapshots/"ui_projection_index.json").write_text('{"row_files":["missing.jsonl"]}',encoding="utf-8")
        doc=load_session(self.session)
        self.assertEqual(doc["events"][0]["payload"]["content"],"长文本")
        self.assertEqual(len(doc["warnings"]),2)
        blob.write_text("changed",encoding="utf-8")
        with self.assertRaises(ImportProblem): load_session(self.session)

    def test_zip_traversal_and_multiple_candidates(self):
        archive=self.root/"bad.zip"
        with zipfile.ZipFile(archive,"w") as z: z.writestr("../events.jsonl","{}")
        with self.assertRaises(ImportProblem): load_session(archive)
        with zipfile.ZipFile(archive,"w") as z:
            for name in ("a","b"): z.writestr(name+"/events.jsonl",(self.session/"events.jsonl").read_bytes())
        with self.assertRaises(ChooseSession) as err: load_session(archive)
        self.assertEqual(err.exception.candidates,["a","b"])
        self.assertEqual(load_session(archive,"b")["session_id"],"test")

    def test_chronological_history_mutations(self):
        events=[event(1,"user_turn_committed",{"content":"old"}),event(2,"ui_event",{"type":"llm_reasoning","content":"r","react_iter":1}),
                event(3,"message_rewritten",{"target_seq":1,"content":"new"}),event(4,"visible_range_changed",{"to_ui_index":1})]
        self.assertEqual(project_history(events[:2])[0]["content"],"old")
        self.assertEqual(project_history(events)[0]["content"],"new")
        self.assertEqual(len(project_history(events)),1)

    def test_legacy_tool_replay_preserves_arguments_and_result(self):
        wire={"type":"execution_update","session_id":"test","run_id":"r1","runtime_seq":4,"seq":4,
              "update":{"execution_id":"tool1","kind":"tool","status":"completed","tool":"read_file",
                        "tool_call_id":"call1","tool_call_index":2,"args":{"path":"a.txt"},"result":"whole result","output":"part"}}
        result=old_wire(wire,{})
        self.assertEqual(result["args"],{"path":"a.txt"})
        self.assertEqual(result["result"],"whole result")
        self.assertEqual(result["tool_call_id"],"call1")
        self.assertEqual(result["index"],2)

    def test_http_import_stream_record_report(self):
        server=ReplayServer(0,self.root/"data")
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(path,body=None,token=True):
            headers={"X-Replay-Token":server.token} if token else {}
            raw=json.dumps(body).encode() if body is not None else None
            with urllib.request.urlopen(urllib.request.Request(server.url+path,raw,headers)) as r:return r.read()
        try:
            catalog=json.loads(request('/api/replay/import',{'path':str(self.session)})); sid=catalog['id']
            unit=next(u for u in catalog['units'] if u['scope']=='text')
            segment=json.loads(request(f'/api/replay/segment?session={sid}&segment={unit["id"]}'))
            stream=request(f'/api/replay/stream?session={sid}&segment={unit["id"]}&version=20261009&speed=8')
            self.assertEqual(stream.count(b'data: '),2)
            saved=json.loads(request('/api/replay/result',{'import_id':sid,'segment_id':unit['id'],'summary':{},'frames':[{'gap_ms':50}], 'markers':[{'kind':'stop'}]}))
            report=request('/api/replay/report.zip?session='+sid)
            with zipfile.ZipFile(io.BytesIO(report)) as z:
                self.assertIn('summary.csv',z.namelist());self.assertIn('records/'+saved['record_id']+'.json',z.namelist())
            records=json.loads(request('/api/replay/results?session='+sid))
            self.assertNotIn('frames',records[0])
            with self.assertRaises(urllib.error.HTTPError) as e: request('/api/replay/import',{},False)
            self.assertEqual(e.exception.code,403)
            e.exception.close()
            with self.assertRaises(urllib.error.HTTPError) as e: request('/api/agent/run',{})
            e.exception.close()
            self.assertIn(b'change-review',request('/api/extensions'))
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_local_aliases_and_restart_token_recovery(self):
        server=ReplayServer(0,self.root/'auth-data')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(host, origin=None, token=None, body=None):
            headers={'Host':host}
            if origin is not None: headers['Origin']=origin
            if token is not None: headers['X-Replay-Token']=token
            raw=json.dumps(body).encode() if body is not None else None
            path='/api/replay/import' if raw else '/api/replay/health'
            with urllib.request.urlopen(urllib.request.Request(server.url+path,raw,headers)) as r:
                return json.loads(r.read())
        try:
            for hostname in ('127.0.0.1','localhost','LOCALHOST'):
                host=f'{hostname}:{server.server_port}'
                health=request(host)
                imported=request(host,'http://'+host,health['token'],{'path':str(self.session)})
                self.assertEqual(imported['name'],'test')
            host=f'127.0.0.1:{server.server_port}'
            old_token=server.token
            server.token='new-server-token'
            with self.assertRaises(urllib.error.HTTPError) as error:
                request(host,'http://'+host,old_token,{'path':str(self.session)})
            self.assertEqual(error.exception.code,403)
            self.assertEqual(json.loads(error.exception.read())['code'],'TOKEN_EXPIRED')
            error.exception.close()
            health=request(host)
            self.assertEqual(request(host,'http://'+host,health['token'],{'path':str(self.session)})['name'],'test')
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_nonlocal_host_and_origin_remain_rejected(self):
        server=ReplayServer(0,self.root/'auth-data')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        local=f'127.0.0.1:{server.server_port}'
        cases=[('attacker.example:'+str(server.server_port),None),
               (local,'https://attacker.example'),(local,'null'),
               (local,'http://localhost:1'),(local,'http://localhost.attacker.example:'+str(server.server_port))]
        try:
            for host,origin in cases:
                headers={'Host':host,'X-Replay-Token':server.token}
                if origin is not None: headers['Origin']=origin
                raw=json.dumps({'path':str(self.session)}).encode()
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(urllib.request.Request(server.url+'/api/replay/import',raw,headers))
                self.assertEqual(json.loads(error.exception.read())['code'],'LOCAL_PAGE_REQUIRED')
                error.exception.close()
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(urllib.request.Request(server.url+'/api/replay/health',headers={'Host':'attacker.example'}))
            error.exception.close()
            self.assertEqual(server.store.catalog(),[])
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_missing_deltas_become_paced_text_without_changing_journal(self):
        for kind,payload in [('ui_event',{'type':'llm_reasoning','react_iter':1,'content':'甲乙'*180}),
                             ('execution_recorded',{'kind':'reasoning','execution_id':'a','react_iter':1,'status':'completed','content':'甲乙'*180})]:
            document=load_session(self.session)
            document['events']=[event(1,'run_started',{}),event(2,kind,payload)]
            s=ReplaySession(document)
            unit=next(u for u in s.units if u['scope']=='text')
            original=s.segment(unit['id'])
            generated=playback_segment(original,True,120)
            self.assertEqual(original['packet_count'],1)
            self.assertEqual(original['duration_ms'],0)
            self.assertTrue(generated['playback']['synthetic'])
            self.assertEqual(generated['duration_ms'],3000)
            texts=[]
            for p in generated['packets']:
                if p.get('synthetic'):
                    wire=p['wire'];texts.append(wire.get('delta') or wire.get('update',{}).get('text_delta'))
                    self.assertEqual(p['original_seq'],2)
                    self.assertEqual(p['original_at_ms'],0)
            self.assertEqual(''.join(texts),payload['content'])
            seqs=[p['seq'] for p in generated['packets']]
            self.assertEqual(seqs,sorted(set(seqs)))
            self.assertFalse(playback_segment(original,False)['playback']['synthetic'])

    def test_recorded_stream_timing_is_preserved(self):
        s=ReplaySession(load_session(self.session))
        unit=next(u for u in s.units if u['scope']=='text')
        original=s.segment(unit['id'])
        generated=playback_segment(original)
        self.assertFalse(generated['playback']['synthetic'])
        self.assertEqual(generated['packets'],original['packets'])


if __name__=='__main__': unittest.main()
