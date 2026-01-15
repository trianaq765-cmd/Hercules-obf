from flask import Flask, request, jsonify, render_template_string
import subprocess
import os
import uuid
import time
import re
from config import Config

app = Flask(__name__)

os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(Config.OUTPUT_FOLDER, exist_ok=True)

def clean_ansi(text):
    return re.sub(r'\x1b\[[0-9;]*m', '', text)

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Hercules Obfuscator</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{font-family:system-ui;background:linear-gradient(135deg,#0f0f23,#1a1a3e);min-height:100vh;color:#fff;padding:20px}
        .container{max-width:900px;margin:0 auto}
        h1{text-align:center;color:#ff6b6b;margin-bottom:30px}
        .card{background:rgba(255,255,255,0.05);border-radius:15px;padding:25px;border:1px solid rgba(255,255,255,0.1);margin-bottom:20px}
        textarea{width:100%;height:200px;padding:15px;border:2px solid rgba(255,107,107,0.3);border-radius:10px;background:rgba(0,0,0,0.3);color:#fff;font-family:monospace}
        select,input{width:100%;padding:12px;border-radius:8px;background:rgba(0,0,0,0.3);color:#fff;border:1px solid rgba(255,255,255,0.2);margin:10px 0}
        label{color:#ff6b6b;display:block;margin:15px 0 8px}
        .btn{background:linear-gradient(135deg,#ff6b6b,#ee5a5a);color:#fff;border:none;padding:15px 40px;font-size:16px;font-weight:bold;border-radius:10px;cursor:pointer;display:inline-block;margin:10px}
        .btn:hover{transform:translateY(-2px)}
        .btn:disabled{opacity:0.5}
        .btn-test{background:linear-gradient(135deg,#00d4ff,#0099cc)}
        .status{padding:15px;border-radius:10px;margin:15px 0;display:none}
        .success{background:rgba(0,255,100,0.1);border:1px solid #00ff64;color:#00ff64;display:block}
        .error{background:rgba(255,0,0,0.1);border:1px solid #ff6464;color:#ff6464;display:block}
        .loading{background:rgba(255,200,0,0.1);border:1px solid #ffc800;color:#ffc800;display:block}
        .debug{background:rgba(0,0,0,0.3);padding:15px;border-radius:10px;margin:15px 0;font-family:monospace;font-size:12px;white-space:pre-wrap;max-height:300px;overflow-y:auto}
        .checkbox{display:flex;align-items:center;gap:10px}
        .checkbox input{width:auto}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ Hercules Obfuscator</h1>
        
        <div class="card">
            <button class="btn btn-test" onclick="runTest()">🧪 Test Hercules</button>
            <div id="testResult" class="debug" style="display:none"></div>
        </div>
        
        <div class="card">
            <label>📄 Lua Code</label>
            <textarea id="code" placeholder="Paste your Lua code here...">print("Hello World")</textarea>
            
            <label>⚡ Preset</label>
            <select id="preset">
                <option value="min" selected>Minimum - Light</option>
                <option value="mid">Medium - Balanced</option>
                <option value="max">Maximum - Heavy</option>
            </select>
            
            <div class="checkbox">
                <input type="checkbox" id="showDebug" checked>
                <label for="showDebug" style="margin:0">Show Debug Info</label>
            </div>
            
            <div style="text-align:center">
                <button class="btn" id="btn" onclick="obfuscate()">🛡️ Obfuscate</button>
            </div>
            
            <div class="status" id="status"></div>
            <div id="debugInfo" class="debug" style="display:none"></div>
            
            <div id="result" style="display:none">
                <label>📤 Output</label>
                <textarea id="output" readonly style="height:300px"></textarea>
                <button class="btn" onclick="download()" style="background:#00d4ff">⬇️ Download</button>
            </div>
        </div>
    </div>
    <script>
    async function runTest() {
        const testResult = document.getElementById('testResult');
        testResult.style.display = 'block';
        testResult.textContent = '🔄 Running tests...';
        
        try {
            const res = await fetch('/api/test');
            const data = await res.json();
            testResult.textContent = data.result;
        } catch(e) {
            testResult.textContent = '❌ Test failed: ' + e.message;
        }
    }
    
    async function obfuscate() {
        const code = document.getElementById('code').value.trim();
        const preset = document.getElementById('preset').value;
        const showDebug = document.getElementById('showDebug').checked;
        const status = document.getElementById('status');
        const debugInfo = document.getElementById('debugInfo');
        const btn = document.getElementById('btn');
        
        if (!code) { 
            status.className = 'status error'; 
            status.textContent = '❌ Enter code!'; 
            return; 
        }
        
        btn.disabled = true; 
        btn.textContent = '⏳ Processing...';
        status.className = 'status loading'; 
        status.textContent = '🔄 Obfuscating...';
        document.getElementById('result').style.display = 'none';
        debugInfo.style.display = 'none';
        
        try {
            const res = await fetch('/api/obfuscate', {
                method: 'POST', 
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({code, preset, debug: showDebug})
            });
            const data = await res.json();
            
            if (data.debug && showDebug) {
                debugInfo.textContent = data.debug;
                debugInfo.style.display = 'block';
            }
            
            if (data.success) {
                status.className = 'status success';
                status.textContent = '✅ Done! Time: ' + data.time_taken + ' | Size: ' + data.original_size + ' → ' + data.obfuscated_size + ' bytes';
                document.getElementById('output').value = data.output;
                document.getElementById('result').style.display = 'block';
            } else {
                status.className = 'status error';
                status.textContent = '❌ ' + data.error;
            }
        } catch(e) {
            status.className = 'status error';
            status.textContent = '❌ ' + e.message;
        }
        
        btn.disabled = false; 
        btn.textContent = '🛡️ Obfuscate';
    }
    
    function download() {
        const blob = new Blob([document.getElementById('output').value], {type: 'text/plain'});
        const a = document.createElement('a'); 
        a.href = URL.createObjectURL(blob);
        a.download = 'obfuscated.lua'; 
        a.click();
    }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/test')
def api_test():
    results = []
    
    # Test 1: Lua version
    try:
        r = subprocess.run(['lua', '-v'], capture_output=True, text=True, timeout=5)
        results.append(f"✅ Lua: {clean_ansi(r.stdout or r.stderr).strip()}")
    except Exception as e:
        results.append(f"❌ Lua: {e}")
    
    # Test 2: Hercules path
    try:
        files = os.listdir(Config.HERCULES_PATH)
        results.append(f"✅ Hercules path exists: {Config.HERCULES_PATH}")
        results.append(f"   Files: {', '.join(files[:10])}")
        if 'hercules.lua' in files:
            results.append("✅ hercules.lua found")
        else:
            results.append("❌ hercules.lua NOT found!")
    except Exception as e:
        results.append(f"❌ Hercules path: {e}")
    
    # Test 3: Hercules help
    try:
        r = subprocess.run(
            ['lua', 'hercules.lua', '--help'],
            cwd=Config.HERCULES_PATH,
            capture_output=True, text=True, timeout=10
        )
        output = clean_ansi(r.stdout or r.stderr)[:500]
        results.append(f"✅ Hercules --help:\n{output}")
    except Exception as e:
        results.append(f"❌ Hercules help: {e}")
    
    # Test 4: Simple obfuscation
    try:
        test_file = os.path.join(Config.UPLOAD_FOLDER, 'test_temp.lua')
        with open(test_file, 'w') as f:
            f.write('print("test")')
        
        r = subprocess.run(
            ['lua', 'hercules.lua', test_file, '--min'],
            cwd=Config.HERCULES_PATH,
            capture_output=True, text=True, timeout=30
        )
        
        output_file = test_file.replace('.lua', '_obfuscated.lua')
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                content = f.read()
            results.append(f"✅ Test obfuscation SUCCESS ({len(content)} bytes)")
            os.remove(output_file)
        else:
            results.append(f"❌ No output file")
            results.append(f"   STDOUT: {clean_ansi(r.stdout)[:200]}")
            results.append(f"   STDERR: {clean_ansi(r.stderr)[:200]}")
        
        os.remove(test_file)
    except Exception as e:
        results.append(f"❌ Test obfuscation: {e}")
    
    return jsonify({'result': '\n'.join(results)})

@app.route('/api/obfuscate', methods=['POST'])
def api_obfuscate():
    debug_info = []
    
    try:
        data = request.json
        code = data.get('code', '')
        preset = data.get('preset', 'min')
        show_debug = data.get('debug', False)
        
        if not code:
            return jsonify({'success': False, 'error': 'No code provided'})
        
        if preset not in ['min', 'mid', 'max']:
            preset = 'min'
        
        req_id = str(uuid.uuid4())[:8]
        input_file = os.path.join(Config.UPLOAD_FOLDER, f'{req_id}.lua')
        
        debug_info.append(f"📁 File: {input_file}")
        debug_info.append(f"📏 Code: {len(code)} bytes")
        debug_info.append(f"⚙️ Preset: {preset}")
        
        with open(input_file, 'w') as f:
            f.write(code)
        
        cmd = ['lua', 'hercules.lua', input_file, f'--{preset}']
        debug_info.append(f"🔧 Command: {' '.join(cmd)}")
        
        start = time.time()
        result = subprocess.run(
            cmd, 
            cwd=Config.HERCULES_PATH, 
            capture_output=True, 
            text=True, 
            timeout=Config.OBFUSCATION_TIMEOUT
        )
        elapsed = time.time() - start
        
        debug_info.append(f"⏱️ Time: {elapsed:.2f}s")
        debug_info.append(f"📤 Exit: {result.returncode}")
        
        stdout = clean_ansi(result.stdout or '')
        stderr = clean_ansi(result.stderr or '')
        
        if stdout:
            debug_info.append(f"📝 STDOUT:\n{stdout[:300]}")
        if stderr:
            debug_info.append(f"⚠️ STDERR:\n{stderr[:300]}")
        
        # Find output
        output_file = None
        base_name = f'{req_id}_obfuscated.lua'
        
        locations = [
            input_file.replace('.lua', '_obfuscated.lua'),
            os.path.join(Config.HERCULES_PATH, base_name),
            os.path.join(Config.UPLOAD_FOLDER, base_name),
        ]
        
        # Scan for any obfuscated file
        for d in [Config.HERCULES_PATH, Config.UPLOAD_FOLDER]:
            try:
                for f in os.listdir(d):
                    if '_obfuscated.lua' in f:
                        locations.append(os.path.join(d, f))
                        debug_info.append(f"🔍 Found: {f}")
            except:
                pass
        
        for loc in locations:
            if os.path.exists(loc):
                output_file = loc
                debug_info.append(f"✅ Output: {loc}")
                break
        
        if output_file:
            with open(output_file, 'r') as f:
                output = f.read()
            
            os.remove(input_file)
            os.remove(output_file)
            
            return jsonify({
                'success': True,
                'output': output,
                'time_taken': f'{elapsed:.2f}s',
                'original_size': len(code),
                'obfuscated_size': len(output),
                'debug': '\n'.join(debug_info) if show_debug else None
            })
        else:
            os.remove(input_file) if os.path.exists(input_file) else None
            debug_info.append("❌ No output file found")
            return jsonify({
                'success': False, 
                'error': stderr or stdout or 'No output',
                'debug': '\n'.join(debug_info) if show_debug else None
            })
            
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False, 
            'error': 'Timeout',
            'debug': '\n'.join(debug_info)
        })
    except Exception as e:
        debug_info.append(f"❌ Exception: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'debug': '\n'.join(debug_info)
        })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    print(f"Hercules Path: {Config.HERCULES_PATH}")
    print(f"Upload Folder: {Config.UPLOAD_FOLDER}")
    app.run(host='0.0.0.0', port=Config.WEB_PORT, debug=True)
