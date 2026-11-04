"""Caller-owned pending turns, backed by the existing control scheduler."""
from fastapi import HTTPException
import time


def composer_snapshot(data, selected):
    composer=data.get('composer') or {}
    if not isinstance(composer,dict) or set(composer)-{'text','contexts'}:
        raise ValueError('Invalid pending composer')
    text=composer.get('text',data.get('ui_message',data['message']))
    contexts=composer.get('contexts',[])
    if not isinstance(text,str) or len(text)>1_000_000 or not isinstance(contexts,list) or len(contexts)>16:
        raise ValueError('Invalid pending draft')
    pages=[]
    for page in contexts:
        if not isinstance(page,dict):raise ValueError('Invalid pending webpage')
        clean={}
        for key,limit in [('title',1000),('url',16384),('text',128000),('capturedAt',80)]:
            value=page.get(key,'')
            if not isinstance(value,str) or len(value)>limit:raise ValueError('Invalid pending webpage '+key)
            clean[key]=value
        if type(page.get('tabId')) is int and page['tabId']>=0:clean['tabId']=page['tabId']
        pages.append(clean)
    return {'text':text,'contexts':pages,'selectedSkills':selected,
            'uploadIds':[item['id'] for item in data.get('attachments',[]) if isinstance(item,dict) and isinstance(item.get('id'),str)]}


def pending_messages(application,principal,session_id):
    rows=[]
    for operation in application.store.operations(status='queued',session_id=session_id,limit=1000):
        request=operation['request']
        if operation['method']!='session.send' or operation['principal']!=principal.id or not request.get('_browser_pending'):
            continue
        rows.append(pending_item(application,principal,operation))
    return rows


def pending_item(application,principal,operation):
    request=operation['request'];draft=dict(request['_browser_draft']);uploads=[];images=[]
    for identity in draft.pop('uploadIds',[]):
        record=application.store.get('message_uploads',identity)
        if record and record.get('owner')==principal.id:
            uploads.append({'id':identity,'name':record.get('name') or '附件','size':record.get('size',0)})
            if record.get('attachment'):images.append(record['attachment']['attachmentId'])
    draft['uploads']=uploads
    draft['automatic']=request.get('_browser_context',{}).get('automatic',False)
    draft['browser_context']=request.get('_browser_context')
    return {'operationId':operation['id'],'clientId':request.get('_browser_client_id'),'runId':operation['run_id'],'content':request.get('ui_message',''),
            'status':'queued','createdAt':operation['created'],'draft':draft,'images':images}


def started_pending_turns(application,principal,session_id):
    """UI facts for admitted queued turns; never create a run from a draft."""
    result=[]
    for operation in application.store.operations(session_id=session_id,limit=128,newest=True):
        if (operation['method']=='session.send' and operation['principal']==principal.id
                and operation['request'].get('_browser_pending') and operation['status'] not in {'queued','cancelled','rejected'}):
            item=pending_item(application,principal,operation)
            result.append({key:item[key] for key in ('runId','content','images')})
    return result


def cancel_pending(application,principal,session_id,operation_id):
    operation=application.store.get_operation(operation_id)
    if (not operation or operation['session_id']!=session_id or operation['principal']!=principal.id
            or operation['method']!='session.send' or not operation['request'].get('_browser_pending')):
        raise HTTPException(404,'Pending message not found')
    if operation['status']=='cancelled':return {'cancelled':True,'operation_id':operation_id}
    # Never use the general operation.cancel fallback: if the scheduler has
    # already claimed this row, withdrawing a draft must not stop its run.
    if not application.store.update_operation(operation_id,expected='queued',status='cancelled',delivery='cancelled'):
        raise HTTPException(409,'消息已开始执行，未撤回；请使用插话或停止')
    return {'cancelled':True,'operation_id':operation_id}


def edit_pending(application,principal,session_id,operation_id,changes):
    from session_control.store import encoded
    with application.store.transaction() as db:
        operation=application.store.operation(db.execute('SELECT * FROM operations WHERE id=?',(operation_id,)).fetchone())
        if (not operation or operation['session_id']!=session_id or operation['principal']!=principal.id
                or operation['method']!='session.send' or not operation['request'].get('_browser_pending')):
            raise HTTPException(404,'Pending message not found')
        if operation['status']!='queued':raise HTTPException(409,'消息已开始执行，未修改；请使用插话')
        request={**operation['request'],**{key:value for key,value in changes.items() if key in {
            'message','ui_message','attachments','_legacy_user_content','_browser_draft','_browser_context'}}}
        # Keep the immutable admission digest and original queue position. The
        # worker's updated-time CAS rejects any pre-edit request it had read.
        if request!=operation['request']:
            db.execute('UPDATE operations SET request=?,updated=? WHERE id=?',
                (encoded(request),max(time.time(),operation['updated']+0.000001),operation_id))
    return application.store.get_operation(operation_id)
