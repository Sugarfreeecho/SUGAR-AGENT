/* A rejected token means no operation ran. Refresh it once and retry the same
 * request, including a selected File/Blob, when an old tab outlives the server. */
window.createReplayApi = (initialToken = '') => {
    let token = initialToken, refreshing;
    async function refreshToken() {
        if (!refreshing) refreshing = (async () => {
            const response = await fetch('/api/replay/health', {cache:'no-store'});
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '无法连接本机工具');
            token = data.token;
        })().finally(() => {refreshing = null;});
        return refreshing;
    }
    async function api(path, options = {}) {
        const request = {...options, headers:{...options.headers}};
        if (request.body && typeof request.body !== 'string' && !(request.body instanceof Blob)) {
            request.headers['Content-Type'] = 'application/json';
            request.body = JSON.stringify(request.body);
        }
        for (let attempt = 0; attempt < 2; attempt++) {
            request.headers['X-Replay-Token'] = token;
            const response = await fetch(path, request), data = await response.json();
            if (response.ok) {
                if (path === '/api/replay/health') token = data.token;
                return data;
            }
            if (response.status === 403 && data.code === 'TOKEN_EXPIRED' && attempt === 0) {
                await refreshToken();
                continue;
            }
            const error = new Error(data.error || '请求失败'); error.data = data; throw error;
        }
    }
    api.token = () => token;
    return api;
};
