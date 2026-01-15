from flask import Flask, request, jsonify, render_template_string, send_file
import subprocess
import os
import uuid
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
        .container{max-width:1000px;margin:0 auto}
        h1{text-align:center;color:#ff6b6b;margin-bottom:10px;text-shadow:0 0 20px rgba(255,107,107,0.5)}
        .subtitle{text-align:center;color:#888;margin-bottom:30px}
        .card{background:rgba(255,255,255,0.05);border-radius:15px;padding:25px;margin-bottom:20px;border:1px solid rgba(255,255,255,0.1)}
        textarea{width:100%;height:200px;padding:15px;border:2px solid rgba(255,107,107,0.3);border-radius:10px;background:rgba(0,0,0,0.3);color:#fff;font-family:monospace;font-size:14px;resize:vertical}
        textarea:focus{outline:none;border-color:#ff6b6b}
        label{color:#ff6b6b;font-weight:500;display:block;margin-bottom:8px;margin-top:15px}
        select,input[type="file"]{width:100%;padding:12px;border-radius:8px;background:rgba(0,0,0,0.3);color:#fff;border:1px solid rgba(255,255,255,0.2);margin-bottom:10px}
        .modules-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:15px 0}
        .module-item{display:flex;align-items:center;gap:10px;padding:10px;background:rgba(0,0,0,0.2);border-radius:8px}
        .module-item input[type="checkbox"]{width:20px;height:20px;accent-color:#ff6b6b}
        .module-item label{margin:0;color:#fff;font-size:14px}
        .btn{background:linear-gradient(135deg,#ff6b6b,#ee5a5a);color:#fff;border:none;padding:15px 40px;font-size:16px;font-weight:bold;border-radius:10px;cursor:pointer;display:block;margin:20px auto;transition:all 0.3s}
        .btn:hover{transform:translateY(-2px);box-shadow:0 10px 30px rgba(255,107,107,0.4)}
        .btn:disabled{opacity:0.5;cursor:not-allowed;transform:none}
        .status{padding:15px;border-radius:10px;margin:15px 0;display:none}
        .success{background:rgba(0,255,100,0.1);border:1px solid #00ff64;color:#00ff64;display:block}
        .error{background:rgba(255,0,0,0.1);border:1px solid #ff6464;color:#ff6464;display:block}
        .loading{background:rgba(255,200,0,0.1);border:1px solid #ffc800;color:#ffc800;display:block}
        .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:15px}
        .stat-item{background:rgba(0,0,0,0.2);padding:15px;border-radius:10px;text-align:center}
        .stat-value{font-size:24px;font-weight:bold;color:#ff6b6b}
        .stat-label{font-size:12px;color:#888}
        .discord-link{background:#5865F2;text-align:center;padding:15px;border-radius:10px;margin-bottom:20px}
        .discord-link a{color:#fff;text-decoration:none;font-weight:bold}
        .preset-btns{display:flex;gap:10px;justify-content:center;margin:15px 0}
        .preset-btn{padding:10px 20px;border-radius:8px;border:2px solid #ff6b6b;background:transparent;color:#ff6b6b;cursor:pointer;transition:all 0.3s}
        .preset-btn:hover,.preset-btn.active{background:#ff6b6b;color:#fff}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ Hercules Obfuscator</h1>
        <p class="subtitle">Powerful Lua Obfuscation Tool</p>
        
        <div class="discord-link">
            <a href="#">🤖 Use our Discord Bot for easier access!</a>
        </div>
        
        <div class="card">
            <label>📄 Lua Code to Obfuscate</label>
            <textarea id="code" placeholder="Paste your Lua code here..."></textarea>
            
            <label>📁 Or Upload File</label>
            <input type="file" id="fileInput" accept=".lua,.txt">
            
            <label>⚡ Quick Presets</label>
            <div class="preset-btns">
                <button class="preset-btn" onclick="setPreset('min')">Minimum</button>
                <button class="preset-btn active" onclick="setPreset('mid')">Medium</button>
                <button class="preset-btn" onclick="setPreset('max')">Maximum</button>
            </div>
            
            <label>🔧 Modules</label>
            <div class="modules-grid">
                <div class="module-item">
                    <input type="checkbox" id="watermark" checked>
                    <label for="watermark">Watermark</label>
                </div>
                <div class="module-item">
                    <input type="checkbox" id="string_encoding">
                    <label for="string_encoding">String Encoding</label>
                </div>
                <div class="module-item">
                    <input type="checkbox" id="string_to_expressions">
                    <label for="string_to_expressions">String to Expressions</label>
                </div>
                <div class="module-item">
                    <input type="checkbox" id="control_flow" checked>
                    <label for="control_flow">Control Flow</label>
                </div>
                <div class="module-item">
                    <input type="checkbox" id="variable_renaming" checked>
                    <label for="variable_renaming">Variable Renaming</label>
                </div>
                <div class="module-item">
                    <input type="checkbox" id="garbage_code" checked>
                    <label for="garbage_code">Garbage Code</label>
                </div>
                <div class="module-item">
                    <input type="checkbox" id="opaque_predicates" checked>
                    <label for="opaque_predicates">Opaque Predicates</label>
                </div>
                <div class="module-item">
                    <input type="checkbox" id="function_inlining">
                    <label for="function_inlining">Function Inlining</label>
                </div>
                <div class="module-item">
                    <input type="checkbox" id="dynamic_code">
                    <label for="dynamic_code">Dynamic Code</label>
                </div>
                <div class="module-item">
                    <input type="checkbox" id="bytecode_encoding">
                    <label for="bytecode_encoding">Bytecode Encoding</label>
                </div>
                <div class="module-item">
                    <input type="checkbox" id="compressor" checked>
                    <label for="compressor">Compressor</label>
                </div>
                <div class="module-item">
                    <input type="checkbox" id="wrap_in_function" checked>
                    <label for="wrap_in_function">Wrap in Function</label>
                </div>
                <div class="module-item">
                    <input type="checkbox" id="virtual_machine">
                    <label for="virtual_machine">Virtual Machine</label>
                </div>
                <div class="module-item">
                    <input type="checkbox" id="antitamper">
                    <label for="antitamper">Anti-Tamper</label>
                </div>
            </div>
            
            <button class="btn" id="submitBtn" onclick="obfuscate()">🛡️ Obfuscate</button>
            
            <div class="status" id="status"></div>
            
            <div id="resultSection" style="display:none">
                <div class="stats" id="stats"></div>
                <label style="margin-top:20px">📤 Obfuscated Output</label>
                <textarea id="output" readonly style="height:300px"></textarea>
                <button class="btn" onclick="downloadOutput()" style="background:linear-gradient(135deg,#00d4ff,#0099cc)">⬇️ Download</button>
            </div>
        </div>
    </div>
    
    <script>
    const presets = {
        min: ['watermark', 'variable_renaming', 'garbage_code'],
        mid: ['watermark', 'string_encoding', 'variable_renaming', 'control_flow', 'garbage_code', 'opaque_predicates', 'compressor'],
        max: ['watermark', 'string_to_expressions', 'control_flow', 'variable_renaming', 'garbage_code', 'opaque_predicates', 'function_inlining', 'compressor', 'wrap_in_function', 'virtual_machine', 'antitamper']
    };
    
    const allModules = ['watermark', 'string_encoding', 'string_to_expressions', 'control_flow', 'variable_renaming', 'garbage_code', 'opaque_predicates', 'function_inlining', 'dynamic_code', 'bytecode_encoding', 'compressor', 'wrap_in_function', 'virtual_machine', 'antitamper'];
    
    function setPreset(preset) {
        document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
        event.target.classList.add('active');
        
        allModules.forEach(m => {
            document.getElementById(m).checked = presets[preset].includes(m);
        });
    }
    
    document.getElementById('fileInput').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => document.getElementById('code').value = e.target.result;
            reader.readAsText(file);
        }
    });
    
    async function obfuscate() {
        const code = document.getElementById('code').value.trim();
        const status = document.getElementById('status');
        const btn = document.getElementById('submitBtn');
        const resultSection = document.getElementById('resultSection');
        
        if (!code) {
            status.className = 'status error';
            status.textContent = '❌ Please enter some code!';
            return;
        }
        
        const modules = {};
        allModules.forEach(m => {
            modules[m] = document.getElementById(m).checked;
        });
        
        btn.disabled = true;
        btn.textContent = '⏳ Obfuscating...';
        status.className = 'status loading';
        status.textContent = '🔄 Processing... This may take a moment.';
        resultSection.style.display = 'none';
        
        try {
            const response = await fetch('/api/obfuscate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({code, modules})
            });
            
            const data = await response.json();
            
            if (data.success) {
                status.className = 'status success';
                status.textContent = '✅ Obfuscation complete!';
                document.getElementById('output').value = data.output;
                
                document.getElementById('stats').innerHTML = `
                    <div class="stat-item"><div class="stat-value">${data.time_taken || 'N/A'}</div><div class="stat-label">Time Taken</div></div>
                    <div class="stat-item"><div class="stat-value">${data.original_size || code.length}</div><div class="stat-label">Original Size</div></div>
                    <div class="stat-item"><div class="stat-value">${data.obfuscated_size || data.output.length}</div><div class="stat-label">Obfuscated Size</div></div>
                    <div class="stat-item"><div class="stat-value">${data.size_increase || 'N/A'}</div><div class="stat-label">Size Increase</div></div>
                `;
                resultSection.style.display = 'block';
            } else {
                status.className = 'status error';
                status.textContent = '❌ Error: ' + data.error;
            }
        } catch(e) {
            status.className = 'status error';
            status.textContent = '❌ Network error: ' + e.message;
        }
        
        btn.disabled = false;
        btn.textContent = '🛡️ Obfuscate';
    }
    
    function downloadOutput() {
        const output = document.getElementById('output').value;
        if (!output) return;
        
        const blob = new Blob([output], {type: 'text/plain'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'obfuscated.lua';
        a.click();
        URL.revokeObjectURL(url);
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
        modules = data.get('modules', {})
        preset = data.get('preset', None)
        
        if not code:
            return jsonify({'success': False, 'error': 'No code provided'})
        
        if len(code) > Config.MAX_CODE_LENGTH:
            return jsonify({'success': False, 'error': 'Code too long'})
        
        req_id = str(uuid.uuid4())
        input_file = os.path.join(Config.UPLOAD_FOLDER, f'{req_id}.lua')
        output_file = os.path.join(Config.OUTPUT_FOLDER, f'{req_id}_obfuscated.lua')
        
        with open(input_file, 'w') as f:
            f.write(code)
        
        # Build command
        cmd = ['lua', 'hercules.lua', input_file]
        
        # Add preset if specified
        if preset:
            cmd.append(f'--{preset}')
        else:
            # Add individual module flags
            module_flags = {
                'string_encoding': '--stringencoding',
                'variable_renaming': '--variablerenaming',
                'control_flow': '--controlflow',
                'garbage_code': '--garbagecode',
                'opaque_predicates': '--opaquepredicates',
                'function_inlining': '--functioninlining',
                'dynamic_code': '--dynamiccode',
                'bytecode_encoding': '--bytecodeencoding',
                'compressor': '--compressor',
                'wrap_in_function': '--wrapinfunction',
                'virtual_machine': '--virtualmachine',
                'antitamper': '--antitamper',
                'string_to_expressions': '--stringtoexpressions',
                'watermark': '--watermark',
            }
            
            for module, enabled in modules.items():
                if enabled and module in module_flags:
                    cmd.append(module_flags[module])
        
        import time
        start_time = time.time()
        
        result = subprocess.run(
            cmd,
            cwd=Config.HERCULES_PATH,
            capture_output=True,
            text=True,
            timeout=Config.OBFUSCATION_TIMEOUT
        )
        
        elapsed = time.time() - start_time
        
        # Find output file
        expected_output = input_file.replace('.lua', '_obfuscated.lua')
        if not os.path.exists(expected_output):
            # Check in hercules src directory
            hercules_output = os.path.join(Config.HERCULES_PATH, f'{req_id}_obfuscated.lua')
            if os.path.exists(hercules_output):
                expected_output = hercules_output
        
        if os.path.exists(expected_output):
            with open(expected_output, 'r') as f:
                output = f.read()
            
            original_size = len(code)
            obfuscated_size = len(output)
            size_increase = f"{((obfuscated_size - original_size) / original_size * 100):.2f}%" if original_size > 0 else "N/A"
            
            # Cleanup
            os.remove(input_file)
            os.remove(expected_output)
            
            return jsonify({
                'success': True,
                'output': output,
                'time_taken': f"{elapsed:.2f}s",
                'original_size': original_size,
                'obfuscated_size': obfuscated_size,
                'size_increase': size_increase
            })
        else:
            os.remove(input_file) if os.path.exists(input_file) else None
            return jsonify({
                'success': False, 
                'error': result.stderr or result.stdout or 'Obfuscation failed'
            })
    
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Timeout (5 min limit)'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'hercules-obfuscator'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.WEB_PORT)
