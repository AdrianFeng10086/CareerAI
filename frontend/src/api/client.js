const BASE = '';

export async function request(url, { method = 'GET', body, headers = {}, signal, raw = false } = {}) {
  const opts = { method, headers: { ...headers }, signal };
  if (body && !(body instanceof FormData)) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  } else if (body) {
    opts.body = body;
  }
  const res = await fetch(`${BASE}${url}`, opts);
  if (raw) return res;
  const data = await res.json();
  return data;
}

export function get(url, opts) {
  return request(url, { method: 'GET', ...opts });
}

export function post(url, body, opts) {
  return request(url, { method: 'POST', body, ...opts });
}
