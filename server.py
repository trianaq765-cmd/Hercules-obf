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
        .card{background:rgba(255,255,255,0.05);border-radius:15px;padding:25px;border:1px solid rgba(255,255,255,0.1)}
        textarea{width:100%;height:200px;padding:15px;border:2px solid rgba(255,107,107,0.3);border-radius:10px;background:rgba(0,0,0,0.3);color:#fff;font-family:monospace}
        select{width:100%;padding:12px;border-radius:8px;background:rgba(0,0,0,0.3);color:#fff;border:1px solid rgba(255,255,255,0.2);margin:10px 0}
        label{color:#ff6b6b;display:block;margin:15px 0 8px}
        .btn{background:linear-gradient(135deg,#ff6b6b,#ee5a5a);color:#fff;border:none;padding:15px 40px;font-size:16px;font-weight:bold;border-radius:10px;cursor:pointer;display:block;margin:20px auto}
        .btn:hover{transform:translateY(-2px)}
        .btn:disabled{opacity:0.5}
        .status{padding:15px;border-radius:10px;margin:15px 0;display:none}
        .success{background:rgba(0,255,100,0.1);border:1px solid #00ff64;color:#00ff64;display:block}
        .error{background:rgba(255,0,0,0.1);border:1px solid #ff6464;color:#ff6464;display:block}
        .loading{background:rgba(255,200,0,0.1);border:1px solid #ffc800;color:#ffc800;display:block}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ Hercules Obfuscator</h1>
        <div class="card">
            <label>📄 Lua Code</label>
            <textarea id="code" placeholder="Paste your Lua code here..."></textarea>
            
            <label>⚡ Preset</label>
            <select id="preset">
                <option value="min" selected>Minimum - Light obfuscation</option>
                <option value="mid">Medium - Balanced</option>
                <option value="max">Maximum - Heavy obfuscation</option>
            </select>
            
            <button class="btn" id="btn" onclick="obfuscate()">🛡️ Obfuscate</button>
            
            <div class="status" id="status"></div>
            
            <div id="result" style="display:none">
                <label>📤 Output</label>
                <textarea id="output" readonly style="height:300px"></textarea>
                <button class="btn" onclick="download()" style="background:#00d4ff">⬇️ Download</button>
            </div>
        </div>
    </div>
    <script>
    async function obfuscate() {
        const code = document.getElementById('code').value.trim();
        const preset = document.getElementById('preset').value;
        const status = document.getElementById('status');
        const btn = document.getElementById('btn');
        
        if (!code) { status.className = 'status error'; status.textContent = '❌ Enter code!'; return; }
        
        btn.disabled = true; btn.textContent = '⏳ Processing...';
        status.className = 'status loading'; status.textContent = '🔄 Obfuscating...';
        document.getElementById('result').style.display = 'none';
        
        try {
            const res = await fetch('/api/obfuscate', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({code, preset})
            });
            const data = await res.json();
            
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
        
        btn.disabled = false; btn.textContent = '🛡️ Obfuscate';
    }
    function download() {
        const blob = new Blob([document.getElementById('output').value], {type: 'text/plain'});
        const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
        a.download = 'obfuscated.lua'; a.click();
    }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/obfuscate', methods=['POST'])
def api_obfuscate():
    try:
        data = request.json
        code = data.get('code', '')
        preset = data.get('preset', 'min')
        
        if not code:
            return jsonify({'success': False, 'error': 'No code provided'})
        
        # Validate preset
        if preset not in ['min', 'mid', 'max']:
            preset = 'min'
        
        req_id = str(uuid.uuid4())
        input_file = os.path.join(Config.UPLOAD_FOLDER, f'{req_id}.lua')
        
        with open(input_file, 'w') as f:
            f.write(code)
        
        # Use correct preset flags
        cmd = ['lua', 'hercules.lua', input_file, f'--{preset}']
        
        print(f"Running: {' '.join(cmd)}")
        
        start = time.time()
        result = subprocess.run(
            cmd, 
            cwd=Config.HERCULES_PATH, 
            capture_output=True, 
            text=True, 
            timeout=Config.OBFUSCATION_TIMEOUT
        )
        elapsed = time.time() - start
        
        print(f"STDOUT: {result.stdout[:500] if result.stdout else 'None'}")
        print(f"STDERR: {result.stderr[:500] if result.stderr else 'None'}")
        
        # Find output file
        output_file = None
        base_name = os.path.basename(input_file).replace('.lua', '_obfuscated.lua')
        
        possible = [
            input_file.replace('.lua', '_obfuscated.lua'),
            os.path.join(Config.HERCULES_PATH, base_name),
            os.path.join(Config.HERCULES_PATH, f'{req_id}_obfuscated.lua'),
        ]
        
        # Scan hercules directory
        try:
            for f in os.listdir(Config.HERCULES_PATH):
                if '_obfuscated.lua' in f:
                    possible.append(os.path.join(Config.HERCULES_PATH, f))
        except:
            pass
        
        for p in possible:
            if os.path.exists(p):
                output_file = p
                break
        
        if output_file:
            with open(output_file, 'r') as f:
                output = f.read()
            
            # Cleanup
            os.remove(input_file)
            os.remove(output_file)
            
            return jsonify({
                'success': True,
                'output': output,
                'time_taken': f'{elapsed:.2f}s',
                'original_size': len(code),
                'obfuscated_size': len(output)
            })
        else:
            os.remove(input_file) if os.path.exists(input_file) else None
            error = result.stderr or result.stdout or 'No output file generated'
            # Remove ANSI color codes
            error = re.sub(r'\x1b\[[0-9;]*m', '', error)
            return jsonify({'success': False, 'error': error[:500]})
            
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Timeout'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.WEB_PORT)
