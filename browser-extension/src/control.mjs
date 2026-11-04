// Control HTTP envelopes and mutation receipts are different protocol layers.
export function controlResult(data) {
  const error = data?.error;
  if (data?.ok === false || error) throw new Error(typeof error === 'string' ? error : error?.message || data?.detail || '请求失败');
  const result = data?.data ?? data?.result ?? data;
  if (result?.accepted === false || ['failed', 'rejected', 'cancelled'].includes(result?.status)) {
    throw new Error(result.error?.message || result.message || '操作未成功，请重试');
  }
  return result;
}
