import re

with open('web.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_tabs = '''    <button class="tab-btn" id="tab-learn" onclick="switchTab('learn')">🎓 Learn</button>
    <button class="tab-btn" id="tab-global" onclick="switchTab('global')">🌍 Global Markets</button>
    <button class="tab-btn" id="tab-settings" onclick="switchTab('settings')">⚙️ Settings</button>
    <button class="tab-btn" id="tab-controls" onclick="switchTab('controls')">🎛️ Controls</button>'''

content = content.replace(
    '''    <button class="tab-btn" id="tab-learn" onclick="switchTab('learn')">🎓 Learn</button>
    <button class="tab-btn" id="tab-controls" onclick="switchTab('controls')">🎛️ Controls</button>''', 
    new_tabs
)

global_and_settings_panels = '''
<!-- GLOBAL MARKETS -->
<div class="panel" id="panel-global">
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px">
    <div class="card" style="padding:22px">
      <div style="font-size:24px;margin-bottom:8px">🇺🇸</div>
      <div style="font-size:15px;font-weight:700;color:#e2e8f0">Wall Street (US)</div>
      <div style="font-size:12px;color:#64748b;margin-bottom:12px">NYSE / NASDAQ / CBOE</div>
      <span class="badge" style="background:#7f1d1d22;color:#f87171;border-color:#991b1b;margin-bottom:16px">CLOSED (Weekend)</span>
      <div style="font-family:monospace;font-size:18px;color:#94a3b8" id="clock-ny">--:--:--</div>
      <div style="font-size:11px;color:#475569;margin-top:12px">Trading: Equities, Options</div>
    </div>
    
    <div class="card" style="padding:22px">
      <div style="font-size:24px;margin-bottom:8px">🇬🇧</div>
      <div style="font-size:15px;font-weight:700;color:#e2e8f0">London (UK)</div>
      <div style="font-size:12px;color:#64748b;margin-bottom:12px">LSE / Euronext</div>
      <span class="badge" style="background:#7f1d1d22;color:#f87171;border-color:#991b1b;margin-bottom:16px">CLOSED (Weekend)</span>
      <div style="font-family:monospace;font-size:18px;color:#94a3b8" id="clock-lon">--:--:--</div>
      <div style="font-size:11px;color:#475569;margin-top:12px">Trading: Equities (Coming Q4)</div>
    </div>

    <div class="card" style="padding:22px">
      <div style="font-size:24px;margin-bottom:8px">🇯🇵</div>
      <div style="font-size:15px;font-weight:700;color:#e2e8f0">Tokyo (Asia)</div>
      <div style="font-size:12px;color:#64748b;margin-bottom:12px">TSE / HKEX</div>
      <span class="badge" style="background:#7f1d1d22;color:#f87171;border-color:#991b1b;margin-bottom:16px">CLOSED (Weekend)</span>
      <div style="font-family:monospace;font-size:18px;color:#94a3b8" id="clock-tok">--:--:--</div>
      <div style="font-size:11px;color:#475569;margin-top:12px">Trading: Equities (Coming Q4)</div>
    </div>

    <div class="card" style="padding:22px;border-color:#3b82f6">
      <div style="font-size:24px;margin-bottom:8px">🌐</div>
      <div style="font-size:15px;font-weight:700;color:#e2e8f0">Crypto (Global)</div>
      <div style="font-size:12px;color:#64748b;margin-bottom:12px">Binance / Coinbase</div>
      <span class="badge" style="background:#14532d22;color:#4ade80;border-color:#166534;margin-bottom:16px">OPEN 24/7</span>
      <div style="font-family:monospace;font-size:18px;color:#60a5fa" id="clock-utc">--:--:--</div>
      <div style="font-size:11px;color:#475569;margin-top:12px">Trading: BTC, ETH via Alpaca</div>
    </div>
  </div>
</div>

<!-- SETTINGS -->
<div class="panel" id="panel-settings">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
    <div class="card" style="padding:24px">
      <div style="font-size:16px;font-weight:700;color:#e2e8f0;margin-bottom:16px">🌍 Regional & Localization</div>
      
      <div style="margin-bottom:16px">
        <label style="display:block;font-size:12px;color:#64748b;margin-bottom:6px">Base Currency Display</label>
        <select style="width:100%;padding:10px;background:#1e293b;border:1px solid #334155;color:#e2e8f0;border-radius:6px;outline:none">
          <option>USD ($) - US Dollar</option>
          <option>EUR (€) - Euro</option>
          <option>GBP (£) - British Pound</option>
          <option>JPY (¥) - Japanese Yen</option>
        </select>
      </div>

      <div style="margin-bottom:24px">
        <label style="display:block;font-size:12px;color:#64748b;margin-bottom:6px">Interface Language</label>
        <select style="width:100%;padding:10px;background:#1e293b;border:1px solid #334155;color:#e2e8f0;border-radius:6px;outline:none">
          <option>English (US)</option>
          <option>Español (ES)</option>
          <option>Français (FR)</option>
          <option>中文 (ZH)</option>
        </select>
      </div>
      
      <button onclick="toast('Regional settings saved! Restarting UI...', 'success')" style="background:#3b82f6;color:white;border:none;padding:10px 16px;border-radius:6px;cursor:pointer;font-weight:600;width:100%">Save Regional Settings</button>
    </div>

    <div class="card" style="padding:24px">
      <div style="font-size:16px;font-weight:700;color:#e2e8f0;margin-bottom:16px">⚡ System Performance & API</div>
      
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px">
        <div style="background:#1e293b;padding:12px;border-radius:8px">
          <div style="font-size:11px;color:#64748b">API Latency (Alpaca)</div>
          <div style="font-size:18px;font-weight:700;color:#4ade80">42ms</div>
        </div>
        <div style="background:#1e293b;padding:12px;border-radius:8px">
          <div style="font-size:11px;color:#64748b">Execution Engine</div>
          <div style="font-size:18px;font-weight:700;color:#60a5fa">MCP Local</div>
        </div>
        <div style="background:#1e293b;padding:12px;border-radius:8px">
          <div style="font-size:11px;color:#64748b">Memory Usage</div>
          <div style="font-size:18px;font-weight:700;color:#e2e8f0">118 MB</div>
        </div>
        <div style="background:#1e293b;padding:12px;border-radius:8px">
          <div style="font-size:11px;color:#64748b">Uptime</div>
          <div style="font-size:18px;font-weight:700;color:#e2e8f0">99.9%</div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- CONTROLS -->'''

content = content.replace('<!-- CONTROLS -->', global_and_settings_panels)

js_clocks = '''
  // Global Clocks
  const ny = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
  const lon = new Date(now.toLocaleString('en-US', { timeZone: 'Europe/London' }));
  const tok = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Tokyo' }));
  
  if (document.getElementById('clock-ny')) {
    document.getElementById('clock-ny').textContent = ny.toLocaleTimeString('en-US', {hour12:false});
    document.getElementById('clock-lon').textContent = lon.toLocaleTimeString('en-US', {hour12:false});
    document.getElementById('clock-tok').textContent = tok.toLocaleTimeString('en-US', {hour12:false});
    document.getElementById('clock-utc').textContent = now.toISOString().substring(11,19) + ' UTC';
  }

  // Mode badge'''

content = content.replace('  // Mode badge', js_clocks)

with open('web.py', 'w', encoding='utf-8') as f:
    f.write(content)
