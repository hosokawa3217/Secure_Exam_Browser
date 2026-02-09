"""
================================================================                
【Secure Exam Browser - システム仕様書】
================================================================
1. 概要:
   - 試験や特定の作業に集中するための、制限付きセキュアブラウザ。
   - Chromiumエンジン (PyQt6) をベースに構築。
   - セキュリティ強化機能とユーザーエクスペリエンス向上機能を統合。

2. 主要機能:
   - 起動時：開いているすべてのエクスプローラー（フォルダ）を強制終了。
   - 起動中：指定URL (morijyobi.train.tracks.run) をフルスクリーンで表示。
   - 監視：Chrome, Edge, Firefox, Brave の起動をリアルタイム(0.5s)で検知。
   - 制限：検知時、画面を赤色(警告色)に染め、Webコンテンツを隠して操作をロック。
   - フォーカス監視：ウィンドウが非アクティブになると警告音を鳴らしロック。

3. セキュリティ機能:
   - 右クリックメニュー完全無効化（View Source、開発者ツールアクセス阻止）。
   - フレームレス＆常時最前面表示でシステム操作を制限。
   - 外部ブラウザプロセス検知による即座の警告・ロック機能。

4. ユーザー支援機能:
   - ログインID自動保存・入力（JSON設定ファイルによる永続化）。
   - 複数パターンのログインフィールド自動検出・入力。
   - 設定管理インターフェース（キーボードショートカット）。

5. 特殊操作:
   - [復帰ボタン]: プロセスの強制終了を試行し、問題がなければWeb画面へ復帰。
   - [Ctrl + Alt + S]: デバッグ用。警告状態を無視して強制的にURLを表示。
   - [Ctrl + Alt + L]: ログインID設定ダイアログ表示（保存・変更・削除）。
   - [Esc]: 開発用。プログラムを終了する。

6. 技術仕様:
   - 設定ファイル: login_config.json（ログインID永続化）
   - 自動入力遅延: 1秒（ページ読み込み完了後）
   - 監視間隔: 0.5秒（リアルタイム監視）
================================================================
"""

import sys
import psutil
import subprocess
import json
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                             QWidget, QMessageBox, QPushButton, QInputDialog)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, QTimer, Qt, QEvent
from PyQt6.QtGui import QContextMenuEvent

# 監視対象（Google Chrome をリストに復帰させました）
TARGET_BROWSERS = ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe","discord.exe"]

class SecureWebEngineView(QWebEngineView):
    """右クリックメニューを無効化したWebEngineView"""
    def contextMenuEvent(self, event: QContextMenuEvent):
        # 右クリックメニューを完全に無効化
        event.ignore()

class SecureBrowser(QMainWindow):
    def __init__(self):
        super().__init__()

        # 起動時：エクスプローラーをすべて閉じる
        self.close_all_explorers()

        self.setWindowTitle("Secure Browser")
        self.target_url = "https://morijyobi.train.tracks.run/auth/login"
        self.url_loaded = False   
        self.focus_lost = False
        self.config_file = "login_config.json"  

        # ウィンドウ設定：枠なし、フルスクリーン、常に最前面
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

    def close_all_explorers(self):
        """エクスプローラーのウィンドウをすべて閉じる"""
        try:
            subprocess.run(['taskkill', '/F', '/IM', 'explorer.exe', '/FI', 'WINDOWTITLE ne ""'], 
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            print(f"Explorer closing error: {e}")

    def changeEvent(self, event):
        """非アクティブ検知時の警告"""
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
            
            if active_browsers:
                msg = f"警告: ブラウザを検知しました\n\n【 {', '.join(active_browsers)} 】"
            else:
                msg = "警告: 画面のフォーカスが外れました！\n外部操作は禁止されています。"

            self.info_label.setText(f"{msg}\n\n下のボタンを押して復帰してください。")
            
            if self.url_loaded:
                self.browser.hide()
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
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        
        modifiers = event.modifiers()
        if (modifiers & Qt.KeyboardModifier.ControlModifier and 
            modifiers & Qt.KeyboardModifier.AltModifier and event.key() == Qt.Key.Key_S):
            self.focus_lost = False
            self.start_web_content()
        
        # Ctrl + Alt + L: ログインID設定
        if (modifiers & Qt.KeyboardModifier.ControlModifier and 
            modifiers & Qt.KeyboardModifier.AltModifier and event.key() == Qt.Key.Key_L):
            self.setup_login_id()

    def load_saved_login_id(self):
        """保存されたログインIDを読み込む"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('login_id', '')
        except Exception as e:
            print(f"設定ファイル読み込みエラー: {e}")
        return ''

    def save_login_id(self, login_id):
        """ログインIDを保存する"""
        try:
            config = {'login_id': login_id}
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"設定ファイル保存エラー: {e}")
            return False

    def setup_login_id(self):
        """ログインID設定ダイアログを表示"""
        current_id = self.load_saved_login_id()
        login_id, ok = QInputDialog.getText(self, 'ログインID設定', 
                                          'ログインIDを入力してください:', 
                                          text=current_id)
        if ok:
            if login_id.strip():
                if self.save_login_id(login_id.strip()):
                    QMessageBox.information(self, '設定完了', 'ログインIDを保存しました。')
                else:
                    QMessageBox.warning(self, 'エラー', 'ログインIDの保存に失敗しました。')
            else:
                # 空文字列の場合は設定を削除
                if os.path.exists(self.config_file):
                    os.remove(self.config_file)
                QMessageBox.information(self, '設定削除', 'ログインID設定を削除しました。')

    def on_page_loaded(self, success):
        """ページ読み込み完了時のイベント処理"""
        if success and self.target_url in self.browser.url().toString():
            # 少し遅延してから自動入力を実行
            QTimer.singleShot(1000, self.auto_fill_login)

    def auto_fill_login(self):
        """保存されたログインIDでフォームを自動入力"""
        login_id = self.load_saved_login_id()
        if login_id:
            # ログインフィールドを探して自動入力するJavaScript
            javascript = f"""
            (function() {{
                // よく使われるログインフィールドのセレクタを試行
                var selectors = [
                    'input[name="username"]',
                    'input[name="email"]', 
                    'input[name="login"]',
                    'input[name="user"]',
                    'input[type="email"]',
                    'input[id*="username"]',
                    'input[id*="email"]',
                    'input[id*="login"]',
                    'input[class*="username"]',
                    'input[class*="email"]',
                    'input[class*="login"]'
                ];
                
                for (var i = 0; i < selectors.length; i++) {{
                    var element = document.querySelector(selectors[i]);
                    if (element && element.type !== 'password') {{
                        element.value = '{login_id}';
                        element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        element.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        console.log('ログインID自動入力完了: ' + selectors[i]);
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