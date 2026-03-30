import os
import time
import json
import random
import string
import secrets
import threading
import requests
from faker import Faker
from get_token import get_access_token
from patchright.sync_api import sync_playwright
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, request

# =========================================================
# 全局状态管理 (RegistrarService)
# =========================================================
class RegistrarService:
    def __init__(self):
        self.running = False
        self.stop_requested = False
        self.succeeded_tasks = 0
        self.failed_tasks = 0
        self.task_counter = 0
        self.max_tasks = 0
        self.concurrent_flows = 0
        self.thread = None
        self.lock = threading.Lock()

    def start(self, concurrent_flows, max_tasks):
        with self.lock:
            if self.running:
                return False, "已经在运行中"
            self.running = True
            self.stop_requested = False
            self.succeeded_tasks = 0
            self.failed_tasks = 0
            self.task_counter = 0
            self.max_tasks = max_tasks
            self.concurrent_flows = concurrent_flows
            self.thread = threading.Thread(target=self._run_main_loop)
            self.thread.start()
            return True, "注册已开始"

    def stop(self):
        with self.lock:
            if not self.running:
                return False, "并未在运行"
            self.stop_requested = True
            return True, "停止请求已发送"

    def get_status(self):
        with self.lock:
            return {
                "is_running": self.running,
                "stats": {
                    "succeeded": self.succeeded_tasks,
                    "failed": self.failed_tasks,
                    "count": self.task_counter,
                },
                "config": {
                    "concurrent_flows": self.concurrent_flows,
                    "max_tasks": self.max_tasks,
                }
            }

    def _run_main_loop(self):
        try:
            main(self.concurrent_flows, self.max_tasks, self)
        finally:
            with self.lock:
                self.running = False

registrar_service = RegistrarService()

# --- 原有的全局变量 ---
thread_local = threading.local()
cleanup_lock = threading.Lock()
active_browsers = []
active_playwrights = []

# Manager（outlookEmailPlus）推送相关
manager_url = ""
manager_api_key = ""
manager_login_password = ""

# ... [原有函数 generate_strong_password, random_email, get_thread_browser, Outlook_register 保持不变] ...

def push_to_manager(email_addr, password, client_id="", refresh_token=""):
    # [原有 push_to_manager 内容]
    if not manager_url:
        return
    session = requests.Session()
    try:
        login_resp = session.post(
            f"{manager_url}/api/login",
            json={"password": manager_login_password or "admin"},
            timeout=10,
        )
        if login_resp.status_code != 200 or not login_resp.json().get("success"):
            return
        if client_id and refresh_token:
            account_string = f"{email_addr}----{password}----{client_id}----{refresh_token}"
            provider = "outlook"
        else:
            account_string = f"{email_addr}----{password}"
            provider = "outlook"
        payload = {
            "account_string": account_string,
            "group_id": 1,
            "provider": provider,
            "add_to_pool": True,
        }
        session.post(f"{manager_url}/api/accounts", json=payload, timeout=15)
    except:
        pass
    finally:
        session.close()

def generate_strong_password(length=16):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = ''.join(secrets.choice(chars) for _ in range(length))
        if (any(c.islower() for c in password) 
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)
                and any(c in "!@#$%^&*" for c in password)):
            return password

def random_email(length):
    first_char = random.choice(string.ascii_lowercase)
    other_chars = []
    for _ in range(length - 1):  
        if random.random() < 0.07:  
            other_chars.append(random.choice(string.digits))
        else: 
            other_chars.append(random.choice(string.ascii_lowercase))
    return first_char + ''.join(other_chars)

def get_thread_browser():
    if not hasattr(thread_local, "playwright"):
        try:
            p = sync_playwright().start()
            proxy_settings = {"server": proxy, "bypass": "localhost"} if proxy else None
            b = p.chromium.launch(headless=True, args=['--lang=zh-CN'], proxy=proxy_settings)
            thread_local.playwright = p
            thread_local.browser = b
            with cleanup_lock:
                active_browsers.append(b)
                active_playwrights.append(p)
        except Exception as e:
            print(f"启动浏览器失败: {e}")
            return None
    return thread_local.browser

def Outlook_register(page, email, password):
    fake = Faker()
    lastname = fake.last_name()
    firstname = fake.first_name()
    year = str(random.randint(1960, 2005))
    month = str(random.randint(1, 12))
    day = str(random.randint(1, 28))
    try:
        page.goto("https://outlook.live.com/mail/0/?prompt=create_account", timeout=20000, wait_until="domcontentloaded")
        page.get_by_text('同意并继续').wait_for(timeout=30000)
        start_time = time.time()
        page.wait_for_timeout(200)
        page.get_by_text('同意并继续').click(timeout=30000)
    except: 
        return False
    try:
        page.locator('[aria-label="新建电子邮件"]').type(email, delay=50, timeout=10000)
        page.locator('[data-testid="primaryButton"]').click(timeout=5000)
        page.locator('[type="password"]').type(password, delay=50, timeout=10000)
        page.locator('[data-testid="primaryButton"]').click(timeout=5000)
        page.locator('[name="BirthYear"]').fill(year,timeout=10000)
        try:
            page.locator('[name="BirthMonth"]').select_option(value=month,timeout=1000)
            page.locator('[name="BirthDay"]').select_option(value=day)
        except:
            page.locator('[name="BirthMonth"]').click()
            page.locator(f'[role="option"]:text-is("{month}月")').click()
            page.locator('[name="BirthDay"]').click()
            page.locator(f'[role="option"]:text-is("{day}日")').click()
            page.locator('[data-testid="primaryButton"]').click(timeout=5000)
        page.locator('#lastNameInput').type(lastname, delay=50, timeout=10000)
        page.locator('#firstNameInput').fill(firstname, timeout=10000)
        page.locator('[data-testid="primaryButton"]').click(timeout=5000)
        page.locator('span > [href="https://go.microsoft.com/fwlink/?LinkID=521839"]').wait_for(state='detached',timeout=22000)
        page.wait_for_timeout(400)
        if page.get_by_text('一些异常活动').count() or page.get_by_text('此站点正在维护').count() > 0:
            return False
        frame1 = page.frame_locator('iframe[title="验证质询"]')
        frame2 = frame1.frame_locator('iframe[style*="display: block"]')
        for _ in range(0, max_captcha_retries + 1):
            frame2.locator('[aria-label="可访问性挑战"]').click(timeout=15000)
            frame2.locator('[aria-label="再次按下"]').click(timeout=30000)
            try:
                page.locator('.draw').wait_for(state="detached")
                page.wait_for_timeout(8000)
                break
            except:
                continue
        else: 
            return False
    except:
        return False
    print(f'[Success: Email Registration] - {email}@outlook.com')
    return True

def process_single_flow(service=None):
    context = None
    try:
        browser = get_thread_browser()
        if not browser: return False
        context = browser.new_context()
        page = context.new_page()
        email =  random_email(random.randint(12, 14))
        password = generate_strong_password(random.randint(11, 15))
        result = Outlook_register(page, email, password)
        if result and not enable_oauth2:
            push_to_manager(f"{email}@outlook.com", password)
            return True
        elif not result:
            return False
        token_result = get_access_token(page, email)
        if token_result[0]:
            refresh_token, access_token, expire_at =  token_result
            push_to_manager(f"{email}@outlook.com", password, client_id, refresh_token)
            return True
        return False
    except:
        return False
    finally:
        if context: context.close()

def main(concurrent_flows=10, max_tasks=1000, service=None):
    with ThreadPoolExecutor(max_workers=concurrent_flows) as executor:
        running_futures = set()
        while (service is None or not service.stop_requested) and \
              ((service and service.task_counter < max_tasks) or (service is None and False)):
            done_futures = {f for f in running_futures if f.done()}
            for future in done_futures:
                try:
                    if future.result():
                        if service: service.succeeded_tasks += 1
                    else:
                        if service: service.failed_tasks += 1
                except:
                    if service: service.failed_tasks += 1
                running_futures.remove(future)
            
            while len(running_futures) < concurrent_flows and \
                  (service and service.task_counter < max_tasks):
                if service and service.stop_requested: break
                new_future = executor.submit(process_single_flow, service)
                running_futures.add(new_future)
                if service: service.task_counter += 1
            time.sleep(1)

        # 等待剩余任务完成
        for future in running_futures:
            try:
                if future.result():
                    if service: service.succeeded_tasks += 1
                else:
                    if service: service.failed_tasks += 1
            except:
                if service: service.failed_tasks += 1

# =========================================================
# Flask API 控制器
# =========================================================
app = Flask(__name__)

@app.route('/api/status', methods=['GET'])
def api_status():
    status = registrar_service.get_status()
    return jsonify(status)

@app.route('/api/start', methods=['POST'])
def api_start():
    data = request.json or {}
    c = int(data.get('concurrent_flows', concurrent_flows))
    m = int(data.get('max_tasks', max_tasks))
    ok, msg = registrar_service.start(c, m)
    return jsonify({"success": ok, "message": msg})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    ok, msg = registrar_service.stop()
    return jsonify({"success": ok, "message": msg})

if __name__ == '__main__':
    # 加载配置
    with open('config.json', 'r', encoding='utf-8') as f:
        conf = json.load(f) 
    proxy = conf.get('proxy')
    enable_oauth2 = conf.get('enable_oauth2')
    concurrent_flows = conf.get("concurrent_flows", 5)
    max_tasks = conf.get("max_tasks", 100)
    max_captcha_retries = conf.get('max_captcha_retries', 2)
    client_id = conf.get('client_id', '')
    manager_url = conf.get('manager_url', '').rstrip('/')
    manager_login_password = conf.get('manager_login_password', '')

    # 启动 Flask
    print("Registrar API 运行在 http://0.0.0.0:8000")
    app.run(host='0.0.0.0', port=8000)
