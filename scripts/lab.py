#!/usr/bin/env python3
"""声音实验室：本机网页上调参数、试听、把满意的存成预设（presets.json）。
用法：<venv>/bin/python scripts/lab.py [--no-open]   → 浏览器打开 http://localhost:8765"""
import os, sys, json, hashlib, threading, webbrowser, warnings
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kokoro_tts as K

PORT = int(os.environ.get('PORT', 8765))
CLIPS = os.path.join(K.HOME, 'lab-clips')
os.makedirs(CLIPS, exist_ok=True)
LOCK = threading.Lock()  # Kokoro 一次只合成一句
VOICES = ('af_alloy af_aoede af_bella af_heart af_jessica af_kore af_nicole af_nova af_river af_sarah af_sky '
          'am_adam am_echo am_eric am_fenrir am_liam am_michael am_onyx am_puck am_santa '
          'bf_alice bf_emma bf_isabella bf_lily bm_daniel bm_fable bm_george bm_lewis').split()


def preset_list():
    mine = K.user_presets()
    return {n: {**p, 'mine': n in mine} for n, p in K.presets().items()}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype='application/json'):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        return json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')

    def do_GET(self):
        if self.path == '/':
            return self.send(200, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lab.html'), 'rb').read(), 'text/html; charset=utf-8')
        if self.path == '/api/meta':
            return self.send(200, {'voices': VOICES, 'presets': preset_list()})
        if self.path.startswith('/clips/'):
            f = os.path.join(CLIPS, os.path.basename(self.path))
            if os.path.exists(f):
                return self.send(200, open(f, 'rb').read(), 'audio/mpeg')
        self.send(404, {'error': 'not found'})

    def do_POST(self):
        try:
            d = self.body()
            if self.path == '/api/synth':
                text, p = d['text'].strip(), d['params']
                f = hashlib.sha1(json.dumps([text, p], sort_keys=True).encode()).hexdigest()[:16] + '.mp3'
                path = os.path.join(CLIPS, f)
                if not os.path.exists(path):
                    with LOCK:
                        audio, _ = K.render(text, p)
                        K.save(audio, path, p, kbps=96)
                return self.send(200, {'url': '/clips/' + f})
            if self.path == '/api/preset':
                ps = K.user_presets()  # 只改用户预设，内置的不动
                if d.get('delete'):
                    ps.pop(d['name'], None)
                else:
                    ps[d['name']] = {**d['params'], 'note': d.get('note', '')}
                K.save_user_presets(ps)
                return self.send(200, {'presets': preset_list()})
            self.send(404, {'error': 'not found'})
        except Exception as e:
            self.send(500, {'error': f'{type(e).__name__}: {e}'})


if __name__ == '__main__':
    print('预热模型…', flush=True)
    K.pipe('a'), K.pipe('b')
    url = f'http://localhost:{PORT}'
    print(f'声音实验室：{url}   （Ctrl+C 结束）', flush=True)
    if '--no-open' not in sys.argv:
        webbrowser.open(url)
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
