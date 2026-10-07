import cv2
import numpy as np
import subprocess
import time
import os
import sys
import requests
import random
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from datetime import datetime
import gc
import json 
import base64 
import webbrowser

CURRENT_VERSION =  1.1

print("Đây là bản 10.4 mới!")

RAW_VERSION_URL = "https://raw.githubusercontent.com/boozii25/botbot/refs/heads/main/version.txt"
RAW_CODE_URL = "https://raw.githubusercontent.com/boozii25/botbot/refs/heads/main/botbot.py"

def check_for_updates():
    try:
        print(f"🔄 Đang kiểm tra phiên bản mới... (Hiện tại: v{CURRENT_VERSION})")
        req = requests.get(RAW_VERSION_URL, timeout=5)
        latest_version = float(req.text.strip())
        
        if latest_version > CURRENT_VERSION:
            print(f"🚀 Phát hiện phiên bản mới: v{latest_version}. Đang tải xuống...")
            code_req = requests.get(RAW_CODE_URL, timeout=10)
            
            with open(__file__, 'w', encoding='utf-8') as f:
                f.write(code_req.text)
                
            print("✅ Cập nhật thành công! Mở trang Web Điều Khiển mới sau 3 giây...")
            time.sleep(3)
            os.execv(sys.executable, ['python', __file__] + sys.argv[1:])
        else:
            print("✅ Bạn đang sử dụng phiên bản mới nhất!")
    except Exception as e:
        print(f"⚠️ Không thể kiểm tra cập nhật (Lỗi mạng hoặc sai Link). Chạy Offline.")

if not getattr(sys, 'frozen', False): 
    check_for_updates()

# --- THƯ VIỆN LÀM WEB ---
from flask import Flask, jsonify, render_template_string, request
import logging

# --- CONFIGURATION ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DISCORD_WEBHOOK_URL = "" 

SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
DEFAULT_LDCONSOLE = r"C:\LDPlayer\LDPlayer9\ldconsole.exe"
DEFAULT_INTERVAL = "30" 

TEMPLATE_CACHE = {}
CACHE_LOCK = threading.Lock()

try:
    CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW
except AttributeError:
    CREATE_NO_WINDOW = 0x08000000

def get_template(template_name):
    with CACHE_LOCK:
        if template_name not in TEMPLATE_CACHE:
            path = os.path.join(BASE_DIR, template_name)
            img = cv2.imread(path, cv2.IMREAD_COLOR)
            TEMPLATE_CACHE[template_name] = img
        return TEMPLATE_CACHE[template_name]

# ==========================================
# KHỞI TẠO MÁY CHỦ WEB (FLASK)
# ==========================================
flask_app = Flask(__name__)
bot_gui_app = None 

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LDPlayer AutoJoin - Web Manager</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-gray-100 p-4 font-sans relative">
    <div class="max-w-4xl mx-auto">
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-3xl font-bold text-blue-400" data-i18n="title">🛡️ Bot Auto-Join Liên Minh</h1>
            <div class="flex gap-3">
                <button id="lang_btn" onclick="switchLang()" class="bg-gray-700 hover:bg-gray-600 text-white py-2 px-4 rounded transition shadow-lg font-bold">🇻🇳 VN</button>
                <button onclick="openSettings()" class="bg-blue-700 hover:bg-blue-600 text-white py-2 px-4 rounded transition shadow-lg" data-i18n="settings_btn">⚙️ Cài đặt chung</button>
            </div>
        </div>

        <div id="devices" class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <p class="text-center text-gray-400 w-full col-span-full" data-i18n="loading">Đang tải dữ liệu...</p>
        </div>

        <div class="bg-gray-800 rounded-lg p-4 shadow-lg border border-gray-700">
            <h2 class="text-xl font-bold text-green-400 mb-3" data-i18n="logs_title">📝 Nhật ký hoạt động</h2>
            <div id="logs" class="bg-black text-green-500 font-mono text-sm p-3 rounded h-48 overflow-y-auto whitespace-pre-wrap"></div>
        </div>
    </div>

    <!-- MODAL CÀI ĐẶT CHUNG -->
    <div id="settingsModal" class="hidden fixed inset-0 bg-black bg-opacity-80 flex items-center justify-center z-50 p-4">
        <div class="bg-gray-800 p-6 rounded-lg w-full max-w-md border border-gray-600 shadow-2xl overflow-y-auto max-h-[90vh]">
            <h2 class="text-2xl font-bold mb-5 text-green-400 border-b border-gray-700 pb-2" data-i18n="modal_title">⚙️ Cài đặt hệ thống</h2>
            
            <div class="mb-4">
                <label class="block text-sm mb-1 text-gray-300" data-i18n="ld_path">Đường dẫn LDConsole.exe</label>
                <input id="set_ld" type="text" class="w-full bg-gray-900 text-white p-2 rounded border border-gray-600 focus:border-blue-500 outline-none" />
            </div>
            
            <div class="flex gap-4 mb-4">
                <div class="w-1/2">
                    <label class="block text-sm mb-1 text-gray-300" data-i18n="gift_int">Nhận quà (phút)</label>
                    <input id="set_gift" type="number" class="w-full bg-gray-900 text-white p-2 rounded border border-gray-600 focus:border-blue-500 outline-none" />
                </div>
                <div class="w-1/2">
                    <label class="block text-sm mb-1 text-gray-300" data-i18n="standby_int">Standby sau (phút)</label>
                    <input id="set_standby" type="number" class="w-full bg-gray-900 text-white p-2 rounded border border-gray-600 focus:border-blue-500 outline-none" />
                </div>
            </div>

            <div class="border-t border-gray-700 pt-4 mt-2">
                <h3 class="font-bold text-yellow-400 mb-3" data-i18n="sch_title">⏰ Hẹn giờ (Để trống nếu Tắt)</h3>
                <div class="flex gap-4 mb-3">
                    <div class="w-1/2">
                        <label class="block text-sm mb-1 text-gray-300" data-i18n="sch_start">Bắt đầu lúc</label>
                        <input id="set_sch_start" type="time" class="w-full bg-gray-900 text-white p-2 rounded border border-gray-600 focus:border-blue-500 outline-none" />
                    </div>
                    <div class="w-1/2">
                        <label class="block text-sm mb-1 text-gray-300" data-i18n="sch_end">Kết thúc lúc</label>
                        <input id="set_sch_end" type="time" class="w-full bg-gray-900 text-white p-2 rounded border border-gray-600 focus:border-blue-500 outline-none" />
                    </div>
                </div>
                <div class="mb-4">
                    <label class="block text-sm mb-1 text-gray-300" data-i18n="sch_action">Hành động khi Kết thúc</label>
                    <select id="set_sch_action" class="w-full bg-gray-900 text-white p-2 rounded border border-gray-600 focus:border-blue-500 outline-none">
                        <option value="close_ld" data-i18n="act_close">Dừng Bot & Tắt Giả lập</option>
                        <option value="shutdown_pc" data-i18n="act_shutdown">Dừng Bot & TẮT MÁY TÍNH</option>
                    </select>
                </div>
            </div>
            
            <div class="flex justify-end gap-3 mt-4">
                <button onclick="closeSettings()" class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-2 px-4 rounded transition" data-i18n="btn_cancel">Hủy</button>
                <button onclick="saveSettings()" class="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-4 rounded transition" data-i18n="btn_save">Lưu & Áp dụng</button>
            </div>
        </div>
    </div>

    <script>
        // --- BỘ TỪ ĐIỂN ĐA NGÔN NGỮ ---
        const i18n = {
            vi: {
                title: "🛡️ Bot Auto-Join Liên Minh", settings_btn: "⚙️ Cài đặt chung", loading: "Đang tải dữ liệu...",
                logs_title: "📝 Nhật ký hoạt động", modal_title: "⚙️ Cài đặt hệ thống", ld_path: "Đường dẫn LDConsole.exe",
                gift_int: "Nhận quà (phút)", standby_int: "Standby sau (phút)", sch_title: "⏰ Hẹn giờ (Để trống nếu Tắt)",
                sch_start: "Bắt đầu lúc", sch_end: "Kết thúc lúc", sch_action: "Hành động khi Kết thúc",
                act_close: "Dừng Bot & Tắt Giả lập", act_shutdown: "Dừng Bot & TẮT MÁY TÍNH",
                btn_cancel: "Hủy", btn_save: "Lưu & Áp dụng",
                txt_running: "● Đang chạy", txt_stopped: "○ Đã dừng", txt_standby: "⏸ Đang Standby",
                btn_stop: "⏹ Dừng Bot", btn_start: "▶ Chạy Bot", btn_resume: "▶ Tiếp tục Bot",
                btn_screen: "📸 Xem màn hình", btn_restart: "🔄 Khởi động lại Giả lập",
                txt_ap: "Dùng AP", txt_speedup: "Tăng tốc", txt_heal_min: "Heal(phút)", txt_speed: "Tốc độ",
                txt_close_img: "❌ Đóng ảnh", msg_no_device: "Chưa có thiết bị nào. Hãy quét trên app PC!",
                msg_taking: "⏳ Đang chụp...", msg_restart: "Đã gửi lệnh Khởi động lại. Quá trình mất khoảng 60 giây!"
            },
            en: {
                title: "🛡️ Auto-Join Alliance Bot", settings_btn: "⚙️ General Settings", loading: "Loading data...",
                logs_title: "📝 Activity Logs", modal_title: "⚙️ System Settings", ld_path: "LDConsole.exe Path",
                gift_int: "Claim Gifts (min)", standby_int: "Standby after (min)", sch_title: "⏰ Schedule (Blank = Off)",
                sch_start: "Start Time", sch_end: "End Time", sch_action: "Action on End",
                act_close: "Stop Bot & Close Emulator", act_shutdown: "Stop Bot & SHUTDOWN PC",
                btn_cancel: "Cancel", btn_save: "Save & Apply",
                txt_running: "● Running", txt_stopped: "○ Stopped", txt_standby: "⏸ Standby",
                btn_stop: "⏹ Stop Bot", btn_start: "▶ Start Bot", btn_resume: "▶ Resume Bot",
                btn_screen: "📸 View Screen", btn_restart: "🔄 Restart Emulator",
                txt_ap: "Use AP", txt_speedup: "Speedups", txt_heal_min: "Heal(min)", txt_speed: "Speed",
                txt_close_img: "❌ Close Image", msg_no_device: "No devices found. Please scan on Desktop app!",
                msg_taking: "⏳ Taking...", msg_restart: "Restart command sent. It takes around 60 seconds!"
            }
        };

        let currentLang = localStorage.getItem('botLang') || 'vi';

        function applyLang() {
            document.querySelectorAll('[data-i18n]').forEach(el => {
                let key = el.getAttribute('data-i18n');
                if (i18n[currentLang][key]) {
                    if (el.tagName === 'OPTION') {
                        el.innerText = i18n[currentLang][key];
                    } else {
                        el.innerText = i18n[currentLang][key];
                    }
                }
            });
            document.getElementById('lang_btn').innerText = currentLang === 'vi' ? '🇻🇳 VN' : '🇬🇧 EN';
        }

        function switchLang() {
            currentLang = currentLang === 'vi' ? 'en' : 'vi';
            localStorage.setItem('botLang', currentLang);
            applyLang();
            loadData();
        }

        function t(key) { return i18n[currentLang][key]; }

        document.addEventListener('DOMContentLoaded', applyLang);

        // ------------------------------------------

        let screenshots = {};

        function action(type, port) {
            if(type === 'restart') alert(t('msg_restart'));
            fetch(`/api/${type}/${port}`).then(() => loadData());
        }

        function takeScreenshot(port) {
            let btn = document.getElementById('btn_screen_' + port);
            if(btn) { btn.innerText = t('msg_taking'); btn.classList.add('opacity-50', 'cursor-not-allowed'); }
            fetch(`/api/screenshot/${port}`).then(r => r.json()).then(res => {
                if(res.status === 'ok') { screenshots[port] = res.image; loadData(); } 
                else {
                    alert(res.message || "Lỗi chụp ảnh!");
                    if(btn) { btn.innerText = t('btn_screen'); btn.classList.remove('opacity-50', 'cursor-not-allowed'); }
                }
            }).catch(e => {
                alert("Mất kết nối tới bot!");
                if(btn) { btn.innerText = t('btn_screen'); btn.classList.remove('opacity-50', 'cursor-not-allowed'); }
            });
        }

        function clearScreenshot(port) { delete screenshots[port]; loadData(); }

        function changeHeal(port, delta) {
            let current = parseFloat(document.getElementById(`heal_val_${port}`).innerText);
            let next = Math.max(0, current + delta);
            updateTabConfig(port, {heal_interval: next});
        }

        function changeSpeed(port, delta) {
            let current = parseFloat(document.getElementById(`speed_val_${port}`).innerText);
            let next = Math.round((current + delta) * 10) / 10;
            updateTabConfig(port, {speed_boost: next});
        }

        function toggleTabCheckboxes(port) { updateTabConfig(port, {}); }

        function updateTabConfig(port, overrides) {
            let use_ap = document.getElementById('use_ap_' + port).checked;
            let use_speedup = document.getElementById('use_speedup_' + port).checked;
            let heal_interval = parseFloat(document.getElementById(`heal_val_${port}`).innerText);
            let speed_boost = parseFloat(document.getElementById(`speed_val_${port}`).innerText);
            
            let payload = {
                use_ap: use_ap, use_speedup: use_speedup, heal_interval: heal_interval, speed_boost: speed_boost, ...overrides
            };
            fetch(`/api/tab_config/${port}`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) }).then(() => loadData());
        }

        function loadData() {
            fetch('/api/status').then(r => r.json()).then(res => {
                if(res.devices.length === 0) {
                    document.getElementById('devices').innerHTML = `<p class="text-center text-red-400 w-full col-span-full mt-4">${t('msg_no_device')}</p>`;
                } else {
                    let html = '';
                    res.devices.forEach(d => {
                        let status = d.is_running ? 
                            (d.is_standby ? `<span class="text-yellow-400 text-sm font-bold animate-pulse">${t('txt_standby')}</span>` : `<span class="text-green-400 text-sm font-bold">${t('txt_running')}</span>`) 
                            : `<span class="text-gray-400 text-sm font-bold">${t('txt_stopped')}</span>`;

                        let btn = d.is_running
                            ? `<button onclick="action('stop', '${d.port}')" class="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 rounded w-full transition mb-2">${t('btn_stop')}</button>`
                            : `<button onclick="action('start', '${d.port}')" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded w-full transition mb-2">${t('btn_start')}</button>`;
                            
                        if(d.is_running && d.is_standby) btn += `<button onclick="action('resume', '${d.port}')" class="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded w-full transition mb-2">${t('btn_resume')}</button>`;
                        if(d.is_running) btn += `<button id="btn_screen_${d.port}" onclick="takeScreenshot('${d.port}')" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded w-full transition text-sm mb-2">${t('btn_screen')}</button>`;
                        btn += `<button onclick="action('restart', '${d.port}')" class="bg-yellow-600 hover:bg-yellow-700 text-white font-bold py-2 px-4 rounded w-full transition text-sm mb-3">${t('btn_restart')}</button>`;

                        let apChecked = d.use_ap ? "checked" : "";
                        let speedupChecked = d.use_speedup ? "checked" : "";
                        let speedSign = d.speed_boost > 0 ? "+" : "";

                        let configControls = `
                            <div class="flex gap-2 mb-3">
                                <label class="flex items-center cursor-pointer bg-gray-900 p-2 rounded border border-gray-700 w-1/2 justify-between">
                                    <span class="text-xs font-bold text-gray-300">${t('txt_ap')}</span>
                                    <input type="checkbox" id="use_ap_${d.port}" onchange="toggleTabCheckboxes('${d.port}')" class="sr-only peer" ${apChecked}>
                                    <div class="w-8 h-4 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-red-500 relative"></div>
                                </label>
                                <label class="flex items-center cursor-pointer bg-gray-900 p-2 rounded border border-gray-700 w-1/2 justify-between">
                                    <span class="text-xs font-bold text-gray-300">${t('txt_speedup')}</span>
                                    <input type="checkbox" id="use_speedup_${d.port}" onchange="toggleTabCheckboxes('${d.port}')" class="sr-only peer" ${speedupChecked}>
                                    <div class="w-8 h-4 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-green-500 relative"></div>
                                </label>
                            </div>
                            <div class="flex gap-2 mb-3">
                                <div class="bg-gray-900 p-2 rounded border border-gray-700 w-1/2 flex justify-between items-center">
                                    <span class="text-xs font-bold text-gray-300">${t('txt_heal_min')}</span>
                                    <div class="flex items-center">
                                        <button onclick="changeHeal('${d.port}', -1)" class="bg-gray-700 hover:bg-gray-600 text-white px-2 rounded">-</button>
                                        <span id="heal_val_${d.port}" class="mx-2 text-sm font-bold text-green-400">${d.heal_interval}</span>
                                        <button onclick="changeHeal('${d.port}', 1)" class="bg-gray-700 hover:bg-gray-600 text-white px-2 rounded">+</button>
                                    </div>
                                </div>
                                <div class="bg-gray-900 p-2 rounded border border-gray-700 w-1/2 flex justify-between items-center">
                                    <span class="text-xs font-bold text-gray-300">${t('txt_speed')}</span>
                                    <div class="flex items-center">
                                        <button onclick="changeSpeed('${d.port}', -0.1)" class="bg-gray-700 hover:bg-gray-600 text-white px-2 rounded">-</button>
                                        <span id="speed_val_${d.port}" class="mx-2 text-sm font-bold text-purple-400">${speedSign}${d.speed_boost.toFixed(1)}</span>
                                        <button onclick="changeSpeed('${d.port}', 0.1)" class="bg-gray-700 hover:bg-gray-600 text-white px-2 rounded">+</button>
                                    </div>
                                </div>
                            </div>
                        `;

                        let screenHtml = '';
                        let screenClass = 'hidden';
                        if(screenshots[d.port]) {
                            screenClass = '';
                            screenHtml = `
                                <img src="data:image/jpeg;base64,${screenshots[d.port]}" class="w-full rounded border border-gray-600 shadow-md" />
                                <button onclick="clearScreenshot('${d.port}')" class="mt-2 text-xs font-bold text-red-400 hover:text-red-300 w-full py-1 bg-gray-900 rounded">${t('txt_close_img')}</button>
                            `;
                        }

                        html += `
                        <div class="bg-gray-800 rounded-lg p-4 shadow-lg border border-gray-700">
                            <div class="flex justify-between items-center mb-3 border-b border-gray-700 pb-2">
                                <h3 class="text-xl font-bold text-blue-300">${d.name}</h3>
                                ${status}
                            </div>
                            <div class="grid grid-cols-2 gap-2 text-sm mb-3">
                                <div class="bg-gray-700 p-2 rounded flex justify-between"><span>⚔ Rally:</span> <span class="text-blue-400 font-bold">${d.rally}</span></div>
                                <div class="bg-gray-700 p-2 rounded flex justify-between"><span>🏥 Heal:</span> <span class="text-green-400 font-bold">${d.heal}</span></div>
                                <div class="bg-gray-700 p-2 rounded flex justify-between"><span>⚡ AP:</span> <span class="text-red-400 font-bold">${d.ap}</span></div>
                                <div class="bg-gray-700 p-2 rounded flex justify-between"><span>⏳ Gift:</span> <span class="text-purple-400 font-bold">${d.timer}</span></div>
                            </div>
                            ${configControls}
                            ${btn}
                            <div id="screen_div_${d.port}" class="${screenClass} mt-2 text-center bg-gray-900 p-2 rounded">
                                ${screenHtml}
                            </div>
                        </div>`;
                    });
                    document.getElementById('devices').innerHTML = html;
                }
                document.getElementById('logs').innerHTML = res.logs.join('\\n');
            }).catch(e => console.log("Đang kết nối lại..."));
        }

        function openSettings() {
            fetch('/api/settings').then(r=>r.json()).then(res => {
                document.getElementById('set_ld').value = res.ldconsole_path;
                document.getElementById('set_gift').value = res.gift_interval;
                document.getElementById('set_standby').value = res.standby_timeout;
                document.getElementById('set_sch_start').value = res.schedule_start;
                document.getElementById('set_sch_end').value = res.schedule_end;
                document.getElementById('set_sch_action').value = res.schedule_action;
                document.getElementById('settingsModal').classList.remove('hidden');
            });
        }

        function closeSettings() { document.getElementById('settingsModal').classList.add('hidden'); }

        function saveSettings() {
            let data = {
                ldconsole_path: document.getElementById('set_ld').value,
                gift_interval: document.getElementById('set_gift').value,
                standby_timeout: document.getElementById('set_standby').value,
                schedule_start: document.getElementById('set_sch_start').value,
                schedule_end: document.getElementById('set_sch_end').value,
                schedule_action: document.getElementById('set_sch_action').value
            };
            fetch('/api/settings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            }).then(r=>r.json()).then(res => {
                alert('✅ Đã lưu cấu hình thành công!');
                closeSettings();
            });
        }

        setInterval(loadData, 2000); 
        loadData();
    </script>
</body>
</html>
"""

@flask_app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@flask_app.route('/api/status')
def api_status():
    if not bot_gui_app: return jsonify({"devices": [], "logs": []})
    
    data = []
    for port, name in bot_gui_app.tab_names.items():
        bot = bot_gui_app.bots.get(port)
        if bot:
            data.append({
                "port": port, "name": name,
                "rally": bot.stats['rally'], "heal": bot.stats['heal'], "ap": bot.stats['ap'],
                "timer": bot.get_next_gift_countdown(),
                "is_running": bot.is_running, "is_standby": bot.is_standby,
                "use_ap": bot.use_ap, "use_speedup": bot.use_speedup,
                "heal_interval": bot.heal_interval_min, "speed_boost": bot.speed_boost
            })
        else:
            data.append({
                "port": port, "name": name,
                "rally": 0, "heal": 0, "ap": 0, "timer": "--:--",
                "is_running": False, "is_standby": False,
                "use_ap": bot_gui_app.use_ap_modes.get(port, True),
                "use_speedup": bot_gui_app.use_speedup_modes.get(port, True),
                "heal_interval": bot_gui_app.heal_intervals.get(port, 3),
                "speed_boost": bot_gui_app.speed_boosts.get(port, 0.0)
            })
    return jsonify({"devices": data, "logs": list(bot_gui_app.recent_logs)})

@flask_app.route('/api/screenshot/<port>')
def api_screenshot(port):
    if not bot_gui_app or port not in bot_gui_app.bots:
        return jsonify({"status": "error", "message": "Bot chưa chạy, không thể chụp."})
    bot = bot_gui_app.bots[port]
    if not bot.is_running: return jsonify({"status": "error", "message": "Hãy bấm Chạy Bot trước khi xem màn hình."})
        
    b64_img = bot.get_base64_screen()
    if b64_img: return jsonify({"status": "ok", "image": b64_img})
    return jsonify({"status": "error", "message": "Không thể chụp màn hình lúc này (Mạng ADB đang bận)."})

@flask_app.route('/api/tab_config/<port>', methods=['POST'])
def api_tab_config(port):
    if bot_gui_app:
        data = request.json
        bot_gui_app.use_ap_modes[port] = data.get('use_ap', True)
        bot_gui_app.use_speedup_modes[port] = data.get('use_speedup', True)
        bot_gui_app.heal_intervals[port] = int(data.get('heal_interval', 3))
        bot_gui_app.speed_boosts[port] = float(data.get('speed_boost', 0.0))
        
        if port in bot_gui_app.bots:
            bot_gui_app.bots[port].use_ap = bot_gui_app.use_ap_modes[port]
            bot_gui_app.bots[port].use_speedup = bot_gui_app.use_speedup_modes[port]
            bot_gui_app.bots[port].heal_interval_min = bot_gui_app.heal_intervals[port]
            bot_gui_app.bots[port].speed_boost = bot_gui_app.speed_boosts[port]
    return jsonify({"status": "ok"})

@flask_app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    if not bot_gui_app: return jsonify({"status": "error"})
        
    if request.method == 'GET':
        return jsonify({
            "ldconsole_path": bot_gui_app.settings.get("ldconsole_path", DEFAULT_LDCONSOLE),
            "gift_interval": bot_gui_app.settings.get("gift_interval", DEFAULT_INTERVAL),
            "standby_timeout": str(bot_gui_app.settings.get("standby_timeout", "30")),
            "schedule_start": bot_gui_app.settings.get("schedule_start", ""),
            "schedule_end": bot_gui_app.settings.get("schedule_end", ""),
            "schedule_action": bot_gui_app.settings.get("schedule_action", "close_ld")
        })
    else:
        data = request.json
        bot_gui_app.settings['ldconsole_path'] = data.get('ldconsole_path', '')
        bot_gui_app.settings['gift_interval'] = data.get('gift_interval', '30')
        try: bot_gui_app.settings['standby_timeout'] = int(data.get('standby_timeout', 30))
        except ValueError: bot_gui_app.settings['standby_timeout'] = 30
            
        bot_gui_app.settings['schedule_start'] = data.get('schedule_start', '')
        bot_gui_app.settings['schedule_end'] = data.get('schedule_end', '')
        bot_gui_app.settings['schedule_action'] = data.get('schedule_action', 'close_ld')
        
        bot_gui_app.save_settings(); bot_gui_app.safe_log("🔧 Đã cập nhật Cài đặt hệ thống từ Web.")
        return jsonify({"status": "ok"})

@flask_app.route('/api/start/<port>')
def api_start(port):
    if bot_gui_app: bot_gui_app.start_bot(port)
    return jsonify({"status": "ok"})

@flask_app.route('/api/stop/<port>')
def api_stop(port):
    if bot_gui_app: bot_gui_app.stop_bot(port)
    return jsonify({"status": "ok"})

@flask_app.route('/api/resume/<port>')
def api_resume(port):
    if bot_gui_app: bot_gui_app.resume_bot(port)
    return jsonify({"status": "ok"})

@flask_app.route('/api/restart/<port>')
def api_restart(port):
    if not bot_gui_app: return jsonify({"status": "error"})
    def restart_task():
        bot_gui_app.stop_bot(port)
        bot_gui_app.safe_log(f"🔄 Đã nhận lệnh Khởi động lại từ Web cho Port {port}...")
        ld_console = bot_gui_app.settings.get('ldconsole_path', '').strip()
        idx = (int(port) - 5555) // 2
        subprocess.run([ld_console, "quit", "--index", str(idx)], creationflags=CREATE_NO_WINDOW); time.sleep(5) 
        subprocess.run([ld_console, "launch", "--index", str(idx)], creationflags=CREATE_NO_WINDOW); time.sleep(60)
        bot_gui_app.safe_log(f"✅ LDPlayer đã sẵn sàng. Tự động kích hoạt Bot...")
        bot_gui_app.start_bot(port)
    threading.Thread(target=restart_task, daemon=True).start()
    return jsonify({"status": "ok"})


# ==========================================
# BOT CLASS
# ==========================================
class BotInstance:
    def __init__(self, port, instance_name, log_callback, ldconsole_path, adb_path, gift_interval_minutes, standby_timeout_minutes, use_ap=True, use_speedup=True, heal_interval_min=3, speed_boost=0.0):
        self.port = port
        self.instance_name = instance_name 
        self.device_id = f"127.0.0.1:{port}"
        self.is_running = False
        self.is_standby = False
        self.standby_notified = False
        self.screen_fails = 0 
        self.adb_lock = threading.Lock()
        
        self.log_callback = log_callback
        self.ldconsole_path = ldconsole_path
        self.adb_path = adb_path 
        self.stats = {'rally': 0, 'heal': 0, 'ap': 0}
        
        self.gift_interval_sec = gift_interval_minutes * 60
        self.standby_timeout_sec = standby_timeout_minutes * 60
        self.use_ap = use_ap
        self.use_speedup = use_speedup
        self.heal_interval_min = heal_interval_min
        self.speed_boost = speed_boost
        
        self.last_gift_claim_time = time.time() - self.gift_interval_sec 
        self.last_rally_time = time.time() 
        self.last_map_home_time = time.time() 
        self.last_heal_time = time.time() - (self.heal_interval_min * 60)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_callback(f"[{timestamp}] [{self.instance_name}]: {message}")

    def send_discord_with_image(self, message, image_path=None):
        try:
            if not DISCORD_WEBHOOK_URL or "https://discord.com/api/webhooks" not in DISCORD_WEBHOOK_URL: return
            if image_path:
                full_path = os.path.join(BASE_DIR, image_path)
                if os.path.exists(full_path):
                    with open(full_path, 'rb') as f:
                        requests.post(DISCORD_WEBHOOK_URL, files={'file': f}, data={'content': f"🚨 [{self.instance_name}] {message}"}, timeout=10)
                    return
            requests.post(DISCORD_WEBHOOK_URL, data={'content': f"🚨 [{self.instance_name}] {message}"}, timeout=10)
        except Exception: pass

    def get_next_gift_countdown(self):
        if not self.is_running: return "--:--"
        remaining = self.gift_interval_sec - (time.time() - self.last_gift_claim_time)
        if remaining <= 0: return "Sẵn sàng"
        mins, secs = divmod(int(remaining), 60); return f"{mins:02d}:{secs:02d}"

    def human_sleep(self, base_time): 
        adjusted = max(0.1, base_time - self.speed_boost)
        time.sleep(adjusted + random.uniform(0.1, 0.5))

    def run_adb(self, command, timeout_sec=5):
        with self.adb_lock:
            try: subprocess.run([self.adb_path, "-s", self.device_id, "shell"] + command.split(), capture_output=True, stdin=subprocess.DEVNULL, timeout=timeout_sec, creationflags=CREATE_NO_WINDOW)
            except Exception as e: self.log(f"❌ ADB Lỗi: {e}")

    def tap_screen(self, x, y): self.run_adb(f"input tap {x + random.randint(-5, 5)} {y + random.randint(-5, 5)}")

    def scroll_war_list(self):
        duration = random.randint(500, 700)
        start_x, start_y = 640 + random.randint(-10, 10), 500 + random.randint(-10, 10)
        end_y = 350 + random.randint(-20, 20)
        self.run_adb(f"input touchscreen swipe {start_x} {start_y} {start_x} {end_y} {duration}")
        self.human_sleep(1)

    def hard_restart_emulator(self):
        idx = (int(self.port) - 5555) // 2
        subprocess.run([self.ldconsole_path, "quit", "--index", str(idx)], creationflags=CREATE_NO_WINDOW); time.sleep(5)
        if not self.is_running: return
        subprocess.run([self.ldconsole_path, "launch", "--index", str(idx)], creationflags=CREATE_NO_WINDOW); self.log(f"Đã mở lại Tab {idx}. ⏳ Đợi 60 giây để Android tải xong...")
        for _ in range(60):
            if not self.is_running: return
            time.sleep(1)
        self.log("🔄 Đang thiết lập lại kết nối ADB...")
        subprocess.run([self.adb_path, "disconnect", self.device_id], capture_output=True, stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW); time.sleep(2)
        subprocess.run([self.adb_path, "connect", self.device_id], capture_output=True, stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW); time.sleep(3)

    def get_base64_screen(self):
        command = [self.adb_path, "-s", self.device_id, "shell", "screencap", "-p"]
        with self.adb_lock:
            try:
                pipe = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
                image_bytes, _ = pipe.communicate(timeout=6)
                img = cv2.imdecode(np.frombuffer(image_bytes.replace(b'\r\n', b'\n'), np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    height, width = img.shape[:2]
                    img = cv2.resize(img, (width//2, height//2))
                    _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 60])
                    return base64.b64encode(buffer).decode('utf-8')
            except Exception: pass
        return None

    def get_screen(self, retries=3):
        command = [self.adb_path, "-s", self.device_id, "shell", "screencap", "-p"]
        for _ in range(retries):
            with self.adb_lock:
                pipe = None
                try:
                    pipe = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
                    image_bytes, err_bytes = pipe.communicate(timeout=8)
                    if b'offline' in err_bytes or b'offline' in image_bytes or b'not found' in err_bytes:
                        subprocess.run([self.adb_path, "disconnect", self.device_id], capture_output=True, stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW); time.sleep(2)
                        subprocess.run([self.adb_path, "connect", self.device_id], capture_output=True, stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW); time.sleep(3) 
                        continue
                    img = cv2.imdecode(np.frombuffer(image_bytes.replace(b'\r\n', b'\n'), np.uint8), cv2.IMREAD_COLOR)
                    if img is not None: self.screen_fails = 0; return img
                except subprocess.TimeoutExpired:
                    if pipe: pipe.kill()
                    subprocess.run([self.adb_path, "disconnect", self.device_id], capture_output=True, stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([self.adb_path, "connect", self.device_id], capture_output=True, stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
                except Exception: pass
            time.sleep(0.5) 
        self.screen_fails += 1; return None

    def find_only(self, template_name, threshold=0.8, screen=None):
        if screen is None: screen = self.get_screen()
        if screen is None: return None
        template = get_template(template_name)
        if template is None: return None
        res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        return (max_loc[0] + template.shape[1] // 2, max_loc[1] + template.shape[0] // 2) if max_val >= threshold else None

    # MẮT THẦN TÌM ẢNH SONG NGỮ (Dual Template)
    def find_only_dual(self, base_name, threshold=0.8, screen=None):
        if screen is None: screen = self.get_screen()
        if screen is None: return None
        
        loc1 = self.find_only(f"img_fort/{base_name}1.png", threshold, screen)
        if loc1: return loc1
        
        loc2 = self.find_only(f"img_fort/{base_name}2.png", threshold, screen)
        return loc2

    def find_and_click(self, template_name, threshold=0.8, wait_time=1, label="", retries=3):
        for i in range(retries):
            if not self.is_running: return False
            loc = self.find_only(template_name, threshold)
            if loc:
                self.tap_screen(loc[0], loc[1]); self.log(f"✅ Bấm: {label}"); self.human_sleep(wait_time); return True
            time.sleep(0.5)
        return False

    def find_and_click_dual(self, base_name, threshold=0.8, wait_time=1, label="", retries=3):
        for i in range(retries):
            if not self.is_running: return False
            loc = self.find_only_dual(base_name, threshold)
            if loc:
                self.tap_screen(loc[0], loc[1]); self.log(f"✅ Bấm: {label}"); self.human_sleep(wait_time); return True
            time.sleep(0.5)
        return False

    def check_distance_in_roi(self, screen, btn_x, btn_y, btn_h):
        roi_img = screen[max(0, btn_y - 150):btn_y + btn_h + 20, 0:btn_x]
        template = get_template("img_fort/dist_2.png")
        if template is None: return False
        res = cv2.matchTemplate(roi_img, template, cv2.TM_CCOEFF_NORMED)
        return cv2.minMaxLoc(res)[1] >= 0.85

    def check_crash_and_recovery(self):
        loc_app = self.find_only("img_fort/app_icon.png", 0.7)
        if loc_app:
            self.log("🎮 Đang ở màn hình chính! Tự động khởi động game...")
            self.tap_screen(loc_app[0], loc_app[1]); self.log("⏳ Chờ 40 giây để game tải lại...")
            for _ in range(40):
                if not self.is_running: break
                time.sleep(1)
            return True

        loc_reconnect = self.find_only_dual("btn_reconnect", 0.7)
        if loc_reconnect:
            self.log("⚠️ Mất mạng! Đang kết nối lại...")
            self.tap_screen(loc_reconnect[0], loc_reconnect[1]); self.human_sleep(5); return True
        return False

    def handle_ap_recovery(self):
        # Tối ưu: Hạ threshold và có vòng lặp chờ bảng Hết AP hiện lên
        for _ in range(3):
            if not self.is_running: break
            if self.find_only_dual("btn_het_ap", 0.65):
                if self.use_ap:
                    self.log("⚡ Bơm bình AP...")
                    for i in range(3): 
                        # Dùng hàm dual với "btn_use", tự động quét btn_use1.png và btn_use2.png
                        if self.find_and_click_dual("btn_use", 0.65, 0.5, f"Bình AP {i+1}", retries=4): 
                            self.stats['ap'] += 1
                    self.find_and_click("img_fort/btn_close.png", 0.7, 1, "Đóng bảng AP")
                    self.find_and_click("img_fort/btn_launch.png", 0.7, 1, "Xuất quân lại")
                    return True
                else:
                    self.log("⚠️ Hết AP (Tính năng bơm AP bị tắt). Chuyển sang Standby.")
                    self.send_discord_with_image("⚠️ Đã hết AP. Tính năng dùng thuốc bị tắt, Bot chuyển sang Standby.")
                    self.find_and_click("img_fort/btn_close.png", 0.7, 1, "Đóng"); self.find_and_click("img_fort/btn_close.png", 0.7, 1, "Đóng")
                    self.is_standby = True
                    return False
            time.sleep(0.5)
        return False

    def downtime_tasks(self):
        current_time = time.time()
        time_elapsed = current_time - self.last_gift_claim_time
        if time_elapsed >= self.gift_interval_sec:
            self.log("⏳ Đã đến giờ, đi nhận quà Liên minh...")
            self.find_and_click("img_fort/btn_close.png", 0.7, 1, "Đóng menu lót", retries=1)
            if not self.find_only("img_fort/btn_alliance.png", 0.7): self.find_and_click("img_fort/btn_menu.png", 0.7, 1.5, "Mở rộng Menu")
            if self.find_and_click("img_fort/btn_alliance.png", 0.7, 1, "Mở Liên Minh"):
                if self.find_and_click("img_fort/btn_gifts.png", 0.7, 1, "Mở Quà"):
                    # --- LUỒNG NHẬN QUÀ CẢI TIẾN SONG NGỮ ---
                    self.find_and_click_dual("btn_member_chest", 0.7, 1, "Rương Thành Viên")
                    self.find_and_click("img_fort/btn_claim_all.png", 0.7, 1, "Nhận Tất Cả")
                    self.find_and_click_dual("btn_confirm", 0.7, 1, "Xác nhận")
                    self.find_and_click_dual("btn_fort_chest", 0.7, 1, "Rương Pháo Đài")
                    self.find_and_click("img_fort/btn_claim_all.png", 0.7, 1, "Nhận Tất Cả")
                    self.find_and_click_dual("btn_confirm", 0.7, 1, "Xác nhận")
                    # ----------------------------------------
                    self.human_sleep(1)
                self.find_and_click("img_fort/btn_close.png", 0.7, 1, "Đóng"); self.find_and_click("img_fort/btn_close.png", 0.7, 1, "Đóng")
                self.last_gift_claim_time = time.time()
            else: self.log("⚠️ Không tìm thấy nút Liên minh, thử lại ở vòng sau.")

    def find_and_join_rally(self):
        self.log("🔍 Tìm kiếm Rally...")
        
        clicked_launched = self.find_and_click("img_fort/rally_launched.png", 0.7, 1, "Nút Tập Kết Đang Chạy")
        if not clicked_launched:
            self.find_and_click("img_fort/rally_list.png", 0.7, 1, "Nút Danh sách Tập kết")
            
        self.find_and_click("img_fort/btn_sort_dropdown.png", 0.6, 1, "Mở Dropdown Lọc")
        self.find_and_click_dual("option_nearest", 0.6, 1, "Gần nhất")
        
        for page in range(3):
            if not self.is_running: break
            screen = self.get_screen()
            if screen is None: continue
            template = get_template("img_fort/btn_join.png")
            if template is None: break
            h, w = template.shape[:-1]; res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            locations = np.where(res >= 0.8)
            if len(locations[0]) > 0:
                for (btn_x, btn_y) in zip(*locations[::-1]):
                    if not self.is_running: break
                    if self.check_distance_in_roi(screen, btn_x, btn_y, h):
                        self.log("✅ Vào Rally..."); self.tap_screen(btn_x + w // 2, btn_y + h // 2); self.human_sleep(2)
                        if self.find_and_click_dual("btn_new_troop", 0.75, 1, "Quân Mới"):
                            if self.find_and_click("img_fort/btn_launch.png", 0.75, 1, "Xuất quân"):
                                self.handle_ap_recovery()
                                self.find_and_click("img_fort/btn_close.png", 0.7, 1, "Đóng Tab")
                                self.stats['rally'] += 1; self.last_rally_time = time.time()
                                return True
                        self.find_and_click("img_fort/btn_close.png", 0.7, 1, "Đóng")
            if page < 2: self.scroll_war_list()
        self.find_and_click("img_fort/btn_close.png", 0.7, 1, "Đóng"); self.find_and_click("img_fort/btn_close.png", 0.7, 1, "Đóng")
        return False

    def heal_troops(self):
        self.log("🏥 Chữa lính Định Kỳ...")
        self.find_and_click("img_fort/btn_close.png", 0.7, 1, "Đóng menu cũ", retries=1)
        found_hospital = self.find_only("img_fort/heal_icon.png", 0.7)
        if not found_hospital:
            self.find_and_click("img_fort/home_icon.png", 0.75, 2, "Về Thành")
            found_hospital = self.find_only("img_fort/heal_icon.png", 0.7)
            
        if found_hospital:
            self.find_and_click("img_fort/heal_icon.png", 0.7, 2, "Bệnh viện")
            self.find_and_click_dual("btn_heal", 0.65, 1, "Chữa trị")
            self.find_and_click("img_fort/help_icon.png", 0.65, 1, "Trợ giúp")
            
            if self.find_and_click("img_fort/finish_heal_icon.png", 0.65, 1, "Chọn Bệnh viện"):
                if self.use_speedup:
                    if self.find_and_click("img_fort/speed_icon.png", 0.65, 1, "Tăng tốc"):
                        for i in range(15):  
                            if not self.find_and_click_dual("btn_use", 0.65, 0.5, "Dùng Tăng tốc", retries=3):
                                self.log("⏭️ Đã dùng xong hoặc hết Tăng tốc.")
                                break
                        self.find_and_click("img_fort/btn_close.png", 0.65, 1, "Đóng bảng Tăng tốc", retries=2)
                    else:
                        self.log("⏭️ Bỏ qua chuỗi Tăng tốc (Không tìm thấy nút).")
                else:
                    self.log("⏭️ Bỏ qua Tăng tốc (Tính năng bị tắt bởi người dùng).")
        else:
            self.log("⏭️ Bỏ qua Chữa trị (Không thấy Bệnh viện), chuyển thẳng đến Nhận quân.")
        
        if self.find_and_click("img_fort/finish_heal_icon.png", 0.6, 1, "Nhận quân", retries=6): self.stats['heal'] += 1
        self.find_and_click("img_fort/btn_close.png", 0.7, 1, "Thoát Menu Bệnh viện", retries=2)

    def run(self):
        self.is_running = True; self.is_standby = False; self.last_rally_time = time.time(); self.screen_fails = 0
        self.last_map_home_time = time.time()
        
        self.log("🚀 Đang thiết lập kết nối ADB an toàn...")
        subprocess.run([self.adb_path, "disconnect", self.device_id], capture_output=True, stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW); time.sleep(1)
        subprocess.run([self.adb_path, "connect", self.device_id], capture_output=True, stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        
        self.log("⏳ Chờ Android phản hồi lệnh...")
        for _ in range(20):
            if not self.is_running: break
            res = subprocess.run([self.adb_path, "-s", self.device_id, "shell", "echo", "ready"], capture_output=True, stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
            if b'ready' in res.stdout: self.log("✅ Kết nối ADB hoàn tất thành công!"); break
            time.sleep(3)
        self.log("🚀 BOT BẮT ĐẦU VÀO LUỒNG CHÍNH")
        
        while self.is_running:
            try:
                if self.screen_fails >= 5:
                    self.log("🚨 Lỗi mạng ADB nghiêm trọng kéo dài! Tự động khởi động lại Giả lập..."); self.hard_restart_emulator(); self.screen_fails = 0; continue
                if self.is_standby: time.sleep(5); continue
                    
                if time.time() - self.last_rally_time > self.standby_timeout_sec:
                    self.is_standby = True
                    if not self.standby_notified:
                        self.log(f"⏸ Không có Rally trong {self.standby_timeout_sec // 60} phút. Chuyển sang Standby."); self.standby_notified = True
                    continue

                if self.check_crash_and_recovery(): continue
                
                # --- CHỐNG KẸT UI SPAM ESC (WATCHDOG HOME/MAP 30 GIÂY) ---
                is_map_visible = self.find_only("img_fort/map_icon.png", 0.7)
                is_home_visible = self.find_only("img_fort/home_icon.png", 0.7)
                
                if is_map_visible or is_home_visible:
                    self.last_map_home_time = time.time()
                else:
                    if time.time() - self.last_map_home_time > 120:
                        self.log("⚠️ Kẹt màn hình (Không thấy Home/Map). Đang Spam ESC để thoát...")
                        while self.is_running:
                            self.run_adb("input keyevent 4")
                            self.human_sleep(1.0)
                            screen_check = self.get_screen()
                            if self.find_only("img_fort/map_icon.png", 0.7, screen_check) or self.find_only("img_fort/home_icon.png", 0.7, screen_check):
                                self.log("✅ Đã thoát kẹt thành công!")
                                self.last_map_home_time = time.time()
                                break
                        continue
                # ---------------------------------------------------------

                self.find_and_click("img_fort/btn_close.png", 0.7, 1, "Dọn dẹp màn hình", retries=1)
                
                if self.heal_interval_min > 0:
                    if time.time() - self.last_heal_time >= self.heal_interval_min * 60:
                        self.heal_troops()
                        self.last_heal_time = time.time()

                joined_rally = self.find_and_join_rally()
                if not joined_rally: self.downtime_tasks()
                
                gc.collect(); delay = random.randint(5, 10)
                for _ in range(delay):
                    if not self.is_running: break
                    time.sleep(1)
            except Exception as e: self.log(f"⚠️ Lỗi: {e}"); time.sleep(5)

    def stop(self): self.is_running = False; self.is_standby = False; self.log("🛑 DỪNG BOT")
    
    def resume(self): 
        self.is_standby = False; self.standby_notified = False
        self.last_rally_time = time.time()
        self.last_map_home_time = time.time()
        self.log("▶ Đã tiếp tục hoạt động từ chế độ Standby.")

# ==========================================
# GIAO DIỆN MINI DESKTOP (LAUCHER)
# ==========================================
class BotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LDPlayer AutoJoin - Web Manager")
        self.root.geometry("480x280") 
        self.root.resizable(False, False)
        
        self.bots = {}
        self.tab_names = {}
        self.use_ap_modes = {}
        self.use_speedup_modes = {}
        self.heal_intervals = {}
        self.speed_boosts = {}
        self.recent_logs = []
        
        global bot_gui_app
        bot_gui_app = self
        
        self.last_scheduled_start = ""
        self.last_scheduled_end = ""
        self.settings = self.load_settings()
        
        tk.Label(root, text="🛡️ BOT AUTO-JOIN (BẢN WEB)", font=("Arial", 16, "bold"), fg="#2196F3").pack(pady=10)
        
        f_path = tk.Frame(root)
        f_path.pack(pady=5)
        tk.Label(f_path, text="LDConsole:", font=("Arial", 10)).pack(side=tk.LEFT)
        self.entry_ldconsole = tk.Entry(f_path, width=35)
        self.entry_ldconsole.insert(0, self.settings.get("ldconsole_path", DEFAULT_LDCONSOLE))
        self.entry_ldconsole.pack(side=tk.LEFT, padx=5)
        
        tk.Button(root, text="🔍 Quét Thiết bị", command=self.scan_devices, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), height=1, width=20).pack(pady=5)
        
        self.lbl_status = tk.Label(root, text="Chưa có thiết bị nào. Hãy quét thiết bị trước.", fg="gray", font=("Arial", 10))
        self.lbl_status.pack(pady=5)
        
        tk.Button(root, text="🌐 MỞ TRANG ĐIỀU KHIỂN WEB", command=self.open_web, bg="#FF9800", fg="white", font=("Arial", 11, "bold"), height=2, width=30).pack(pady=10)
        
        self.update_timers()
        threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=5000, use_reloader=False), daemon=True).start()

    def open_web(self):
        webbrowser.open("http://localhost:5000")

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except Exception: pass
        return {
            "ldconsole_path": DEFAULT_LDCONSOLE, "gift_interval": DEFAULT_INTERVAL, "standby_timeout": 30,
            "schedule_start": "", "schedule_end": "", "schedule_action": "close_ld"
        }

    def save_settings(self):
        self.settings["ldconsole_path"] = self.entry_ldconsole.get().strip()
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f: json.dump(self.settings, f, indent=4)
        except Exception as e: self.safe_log(f"⚠️ Lỗi lưu cấu hình: {e}")

    def update_timers(self):
        now_hm = datetime.now().strftime("%H:%M")
        start_hm = self.settings.get("schedule_start", "")
        end_hm = self.settings.get("schedule_end", "")
        action = self.settings.get("schedule_action", "close_ld")
        
        if start_hm and now_hm == start_hm and self.last_scheduled_start != start_hm:
            self.last_scheduled_start = start_hm; self.safe_log(f"⏰ ĐẾN GIỜ HẸN ({start_hm}). Tự động CHẠY tất cả các tab đã quét...")
            for port in list(self.tab_names.keys()): self.start_bot(port)
                
        if end_hm and now_hm == end_hm and self.last_scheduled_end != end_hm:
            self.last_scheduled_end = end_hm; self.safe_log(f"⏰ ĐẾN GIỜ KẾT THÚC ({end_hm}). Thực thi: {'Tắt PC' if action == 'shutdown_pc' else 'Tắt Giả lập'}")
            for port in list(self.tab_names.keys()): self.stop_bot(port)
            if action == "shutdown_pc": 
                self.safe_log("🚨 MÁY TÍNH SẼ TỰ ĐỘNG TẮT SAU 60 GIÂY!")
                os.system("shutdown /s /t 60")
            else:
                ld_console = self.entry_ldconsole.get().strip()
                for port in list(self.tab_names.keys()):
                    idx = (int(port) - 5555) // 2
                    subprocess.run([ld_console, "quit", "--index", str(idx)], creationflags=CREATE_NO_WINDOW)

        self.root.after(1000, self.update_timers)

    def safe_log(self, message):
        self.recent_logs.append(message)
        if len(self.recent_logs) > 50: self.recent_logs.pop(0)

    def scan_devices(self):
        self.save_settings()
        self.lbl_status.config(text="Đang lấy dữ liệu từ LDPlayer... (Vui lòng đợi)", fg="blue")
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        ld_console = self.entry_ldconsole.get().strip()
        current_adb_path = os.path.join(os.path.dirname(ld_console), "adb.exe")
        if not os.path.exists(current_adb_path) or not os.path.exists(ld_console):
            self.safe_log("⚠️ LỖI: Đường dẫn LDConsole không hợp lệ!")
            self.root.after(0, lambda: self.lbl_status.config(text="⚠️ Lỗi: Sai đường dẫn LDConsole!", fg="red"))
            return
        
        ld_names = {}
        try:
            res = subprocess.run([ld_console, "list2"], capture_output=True, text=True, encoding='utf-8', errors='ignore', stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
            if res.stdout:
                for line in res.stdout.strip().split('\n'):
                    parts = line.split(',')
                    if len(parts) >= 2 and parts[0].isdigit(): ld_names[int(parts[0])] = parts[1]
        except Exception as e: self.safe_log(f"⚠️ Lỗi đọc tên Tab: {e}")

        try:
            subprocess.run([current_adb_path, "start-server"], capture_output=True, stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
            for port in range(5555, 5575, 2): subprocess.run([current_adb_path, "connect", f"127.0.0.1:{port}"], capture_output=True, stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
            time.sleep(1) 
            result = subprocess.run([current_adb_path, "devices"], capture_output=True, text=True, timeout=5, encoding='utf-8', errors='ignore', stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
            active_ports = [line.split('\t')[0].split(":")[1] for line in result.stdout.strip().split('\n')[1:] if "device" in line and "offline" not in line and "127.0.0.1:" in line]
            
            if not active_ports:
                self.safe_log("⚠️ Không tìm thấy tab giả lập nào.")
                self.root.after(0, lambda: self.lbl_status.config(text="❌ Không tìm thấy thiết bị nào đang bật.", fg="red"))
                return
                
            self.safe_log(f"✅ Đã tìm thấy {len(active_ports)} thiết bị!")
            def update_ui():
                self.tab_names.clear()
                for i, port in enumerate(active_ports):
                    idx = (int(port) - 5555) // 2; instance_name = ld_names.get(idx, f"Tab {port}")
                    self.tab_names[port] = instance_name
                    if port not in self.use_ap_modes: self.use_ap_modes[port] = True
                    if port not in self.use_speedup_modes: self.use_speedup_modes[port] = True
                    if port not in self.heal_intervals: self.heal_intervals[port] = 3
                    if port not in self.speed_boosts: self.speed_boosts[port] = 0.0
                self.lbl_status.config(text=f"✅ Kết nối {len(active_ports)} Tab thành công! Hãy mở Web để điều khiển.", fg="green")
            self.root.after(0, update_ui)
        except Exception as e: 
            self.safe_log(f"⚠️ Lỗi quét: {e}")
            self.root.after(0, lambda: self.lbl_status.config(text="❌ Lỗi khi lấy danh sách thiết bị.", fg="red"))

    def start_bot(self, port):
        if port not in self.bots or not self.bots[port].is_running:
            ld_console = self.entry_ldconsole.get().strip()
            try: gift_interval = int(self.settings.get("gift_interval", 30))
            except ValueError: gift_interval = 30
            standby_timeout = int(self.settings.get("standby_timeout", 30))
            
            use_ap = self.use_ap_modes.get(port, True)
            use_speedup = self.use_speedup_modes.get(port, True)
            heal_int = self.heal_intervals.get(port, 3)
            speed = self.speed_boosts.get(port, 0.0)
            
            adb_path = os.path.join(os.path.dirname(ld_console), "adb.exe")
            instance_name = self.tab_names.get(port, f"Tab {port}")
            
            bot = BotInstance(port, instance_name, self.safe_log, ld_console, adb_path, gift_interval, standby_timeout, use_ap, use_speedup, heal_int, speed)
            self.bots[port] = bot
            threading.Thread(target=bot.run, daemon=True).start()

    def stop_bot(self, port):
        if port in self.bots: self.bots[port].stop()

    def resume_bot(self, port):
        if port in self.bots and self.bots[port].is_standby: self.bots[port].resume()

if __name__ == "__main__":
    root = tk.Tk()
    app = BotApp(root)
    root.mainloop()
