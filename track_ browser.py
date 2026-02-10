"""
================================================================                
【Secure Exam Browser - システム仕様書（最新版）】
================================================================
1. 概要:
   - 試験および特定業務への集中を目的とした、高セキュリティ型ブラウザ。
   - Chromium (PyQt6 WebEngine) を基盤とし、独自の外殻（ラッパー）で保護。

2. セキュリティ・制限機能:
   - 【起動制限】: 起動時に開いているすべてのフォルダ（エクスプローラー）を強制終了。
   - 【音量制御】: 起動時にシステム音量を自動的に50%へ調整し、テスト音を鳴らす。
   - 【アプリ監視】: Chrome, Edge, Firefox, Brave, Discord の起動を常時スキャンし、検知時は画面をロック。
   - 【視覚ブロック】: 不正検知時、Webコンテンツを隠蔽し、警告画面へ切り替え。
   - 【全画面固定】: タスクバーを完全に覆い隠すフルスクリーン表示（最前面固定）。
   - 【フォーカス監視】: ウィンドウが非アクティブになると警告音を鳴らしロック。
   - 【操作制限】: マウスの右クリックメニューを完全に無効化。

3. 利便性向上機能:
   - 【ログインID保存】: 外部ファイル (login_config.json) にログインIDを保存。
   - 【自動入力機能】: ページ読み込み完了時、JavaScriptを注入してログインIDをセット。

4. 特殊操作（管理者・デバッグ用）:
   - [Ctrl + Alt + L]: ログインID設定ダイアログの表示。
   - [Ctrl + Alt + S]: 強制進捗コマンド。
   - [Esc]: プログラムの終了。
================================================================
"""

import sys
import psutil
import subprocess
import json
import os
import ctypes # 音量制御用
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                             QWidget, QMessageBox, QPushButton, QInputDialog)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, QTimer, Qt, QEvent
from PyQt6.QtGui import QContextMenuEvent

# 監視対象
TARGET_BROWSERS = ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe","discord.exe"]

class SecureWebEngineView(QWebEngineView):
    """右クリックメニューを無効化したWebEngineView"""
    def contextMenuEvent(self, event: QContextMenuEvent):
        event.ignore()

class SecureBrowser(QMainWindow):
    def __init__(self):
        super().__init__()

        # --- 起動時の初期化処理 ---
        self.close_all_explorers()
        self.init_system_volume() # 音量を50%にしてテスト鳴動

        self.setWindowTitle("Secure Browser")
        self.target_url = "https://morijyobi.train.tracks.run/auth/login"
        self.url_loaded = False   
        self.focus_lost = False
        self.config_file = "login_config.json"  

        # ウィンドウ設定
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        
        self.central_widget = QWidget()
        self.layout = QVBoxLayout(self.central_widget)
        self.setCentralWidget(self.central_widget)

        self.info_label = QLabel("システムチェック中...")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        self.layout.addWidget(self.info_label)

        self.confirm_button = QPushButton("システムを正常化して開始/復帰")
        self.confirm_button.setStyleSheet("""
            QPushButton {
                font-size: 20px; padding: 15px; background-color: white;
                color: #ff4d4d; border-radius: 10px; font-weight: bold; min-width: 300px;
            }
            QPushButton:hover { background-color: #f0f0f0; }
        """)
        self.confirm_button.clicked.connect(self.on_confirm_click)
        self.confirm_button.hide()
        self.layout.addWidget(self.confirm_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.browser = SecureWebEngineView()
        self.browser.hide()
        self.browser.loadFinished.connect(self.on_page_loaded)
        self.layout.addWidget(self.browser)

        self.showFullScreen()

        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.update_ui_status)
        self.monitor_timer.start(500)

    def init_system_volume(self):
        """システム音量を50%に設定し、テスト音を鳴らす"""
        try:
            # WindowsのSendMessageを使用して音量を調整（0xADはミュート、0xAE/AFは増減）
            # ここではシンプルに、シェル経由で音量を50%に固定する手法をとります
            # (Powershellコマンドをバックグラウンドで実行)
            ps_command = "(new-object -com wscript.shell).SendKeys([char]173); " # 一旦ミュート解除
            ps_command += "$w = new-object -com wscript.shell; for($i=0; $i -lt 50; $i++) { $w.SendKeys([char]175) }; " # 最大まで上げる
            ps_command += "for($i=0; $i -lt 25; $i++) { $w.SendKeys([char]174) }" # 25回下げて約50%にする
            
            subprocess.run(["powershell", "-Command", ps_command], 
                           creationflags=subprocess.CREATE_NO_WINDOW)
            
            # テスト音を鳴らす
            QApplication.beep()
        except Exception as e:
            print(f"Volume Init Error: {e}")

    def close_all_explorers(self):
        try:
            subprocess.run(['taskkill', '/F', '/IM', 'explorer.exe', '/FI', 'WINDOWTITLE ne ""'], 
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            print(f"Explorer closing error: {e}")

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow():
                QApplication.beep()
                self.focus_lost = True
                self.raise_()
                self.activateWindow()
        super().changeEvent(event)

    def get_active_browsers(self):
        found = set()
        for proc in psutil.process_iter(['name']):
            try:
                name = proc.info['name'].lower()
                if name in TARGET_BROWSERS:
                    found.add(name)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return list(found)

    def on_confirm_click(self):
        self.close_all_explorers()
        active_browsers = self.get_active_browsers()
        if active_browsers:
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'].lower() in TARGET_BROWSERS:
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            QTimer.singleShot(800, self.final_check)
        else:
            self.focus_lost = False 
            self.start_web_content()

    def final_check(self):
        if not self.get_active_browsers():
            self.start_web_content()
        else:
            QMessageBox.warning(self, "エラー", "不正なプロセスを終了できませんでした。")

    def start_web_content(self):
        if not self.url_loaded:
            self.browser.setUrl(QUrl(self.target_url))
            self.url_loaded = True
        self.info_label.hide()
        self.confirm_button.hide()
        self.browser.show()
        self.setStyleSheet("QMainWindow { background-color: white; }")

    def update_ui_status(self):
        active_browsers = self.get_active_browsers()
        if active_browsers or self.focus_lost:
            self.setStyleSheet("QMainWindow { background-color: #ff4d4d; }")
            self.info_label.show()
            msg = f"警告: ブラウザを検知しました\n\n【 {', '.join(active_browsers)} 】" if active_browsers else "警告: 画面のフォーカスが外れました！\n外部操作は禁止されています。"
            self.info_label.setText(f"{msg}\n\n下のボタンを押して復帰してください。")
            if self.url_loaded: self.browser.hide()
            self.confirm_button.show()
        else:
            if self.url_loaded:
                self.info_label.hide()
                self.confirm_button.hide()
                self.browser.show()
                self.setStyleSheet("QMainWindow { background-color: white; }")
            else:
                self.info_label.setText("チェック完了。開始できます。")
                self.setStyleSheet("QMainWindow { background-color: #2ecc71; }")
                self.confirm_button.show()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape: self.close()
        modifiers = event.modifiers()
        if (modifiers & Qt.KeyboardModifier.ControlModifier and 
            modifiers & Qt.KeyboardModifier.AltModifier):
            if event.key() == Qt.Key.Key_S:
                self.focus_lost = False
                self.start_web_content()
            elif event.key() == Qt.Key.Key_L:
                self.setup_login_id()

    def load_saved_login_id(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f).get('login_id', '')
        except: pass
        return ''

    def save_login_id(self, login_id):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump({'login_id': login_id}, f, ensure_ascii=False, indent=2)
            return True
        except: return False

    def setup_login_id(self):
        current_id = self.load_saved_login_id()
        login_id, ok = QInputDialog.getText(self, 'ログインID設定', 'ログインIDを入力してください:', text=current_id)
        if ok:
            if login_id.strip():
                self.save_login_id(login_id.strip())
                QMessageBox.information(self, '設定完了', 'ログインIDを保存しました。')
            elif os.path.exists(self.config_file):
                os.remove(self.config_file)

    def on_page_loaded(self, success):
        if success and self.target_url in self.browser.url().toString():
            QTimer.singleShot(1000, self.auto_fill_login)

    def auto_fill_login(self):
        login_id = self.load_saved_login_id()
        if login_id:
            javascript = f"""
            (function() {{
                var selectors = ['input[name="username"]','input[name="email"]','input[name="login"]','input[type="email"]'];
                for (var i = 0; i < selectors.length; i++) {{
                    var el = document.querySelector(selectors[i]);
                    if (el && el.type !== 'password') {{
                        el.value = '{login_id}';
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        break;
                    }}
                }}
            }})();
            """
            self.browser.page().runJavaScript(javascript)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SecureBrowser()
    sys.exit(app.exec())
