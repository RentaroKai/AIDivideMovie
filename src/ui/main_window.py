import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import pathlib
import threading
import os
from typing import Optional
from ..utils.config import config_manager, ConfigError, ModelsConfig
from ..utils.prompt_manager import prompt_manager
from ..utils.path_resolver import get_config_file_path
import json

logger = logging.getLogger(__name__)

class MainWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("動画分割ツール - Video Splitter")
        self.root.geometry("333x210")
        
        # サービスの初期化は動画分割機能実装時に追加
        
        self._create_widgets()
        self._setup_layout()

    def _create_widgets(self):
        """ウィジェットの作成"""
        # スタイルの設定
        style = ttk.Style()
        style.configure(
            "Execute.TButton",
            background="#2F4F4F",  # ダークモスグリーン
            foreground="white"     # 白色
        )
        
        # ファイル選択部分
        self.file_frame = ttk.LabelFrame(self.root, text="入力ファイル", padding=10)
        self.file_path_var = tk.StringVar()
        self.file_path_entry = ttk.Entry(self.file_frame, textvariable=self.file_path_var, width=30)
        self.browse_button = ttk.Button(self.file_frame, text="ファイル選択", command=self._browse_file)
        

        
        # ボタン部分
        self.open_output_button = tk.Button(
            self.root,
            text="📁",
            command=self._open_output_dir,
            relief="raised",
            padx=10,
            pady=5
        )
        
        # 実行ボタン
        self.execute_button = tk.Button(
            self.root,
            text="実行",
            command=self._execute_processing,
            bg="#2F4F4F",  # ダークモスグリーン
            fg="white",    # 白色
            relief="raised",
            padx=10,
            pady=5
        )
        
        # 設定ボタン
        self.settings_button = tk.Button(
            self.root,
            text="設定",
            command=self._show_settings,
            relief="raised",
            padx=10,
            pady=5
        )
        
        # ステータス表示
        self.status_var = tk.StringVar(value="待機中")
        self.status_label = ttk.Label(self.root, textvariable=self.status_var)

    def _setup_layout(self):
        """レイアウトの設定"""
        # ファイル選択部分
        self.file_frame.pack(fill=tk.X, padx=10, pady=5)
        self.file_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.browse_button.pack(side=tk.LEFT)
        

        
        # ボタン部分
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        self.execute_button.pack(side=tk.RIGHT, padx=5)
        self.settings_button.pack(side=tk.RIGHT, padx=5)
        self.open_output_button.pack(side=tk.RIGHT, padx=5)
        
        # ステータス表示
        self.status_label.pack(fill=tk.X, padx=10, pady=5)

    def _browse_file(self):
        """ファイル選択ダイアログを表示"""
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("Gemini対応動画", "*.mp4 *.mpeg *.mov *.avi *.flv *.mpg *.webm *.wmv *.3gp"),
                ("すべてのファイル", "*.*")
            ]
        )
        if file_path:
            self.file_path_var.set(file_path)
            # ファイル形式に応じたステータス表示
            _, ext = os.path.splitext(file_path)
            ext = ext.lower().lstrip('.')
            if ext in ['m4a', 'aac', 'flac', 'ogg', 'mkv', 'avi', 'mov', 'flv']:
                self.status_var.set("注意: このファイル形式は変換が必要です。処理時間が長くなる可能性があります。")
            else:
                self.status_var.set("待機中")

    def _animate_status_label(self):
        """ステータスラベルにアニメーションを表示する"""
        base_text = "処理中"
        current_text = self.status_var.get()
        if current_text.startswith(base_text):
            if current_text == base_text:
                new_text = base_text + "."
            elif current_text == base_text + ".":
                new_text = base_text + ".."
            elif current_text == base_text + "..":
                new_text = base_text + "..."
            else:
                new_text = base_text
            self.status_var.set(new_text)
            if self.status_var.get().startswith(base_text):
                self.root.after(500, self._animate_status_label)

    def _execute_processing(self):
        """処理の実行"""
        if not self.file_path_var.get():
            messagebox.showerror("エラー", "ファイルを選択してください。")
            return
        
        # UIの更新
        self.execute_button.config(state="disabled")
        self.status_var.set("処理中...")
        self._animate_status_label()
        
        # 処理の実行（別スレッド）
        thread = threading.Thread(target=self._process_video_split)
        thread.start()

    def _process_video_split(self):
        """動画分割処理の実行（別スレッド）"""
        try:
            input_file = pathlib.Path(self.file_path_var.get())
            
            # 動画分割処理の実行
            from ..services.video_splitter import VideoSplitter, VideoSplitterError
            
            self.root.after(0, lambda: self.status_var.set("動画解析中..."))
            
            video_splitter = VideoSplitter()
            results = video_splitter.split_video(str(input_file))
            
            # 成功メッセージ
            self.root.after(0, lambda: messagebox.showinfo(
                "動画分割完了",
                f"動画分割処理が完了しました！\n\n"
                f"入力ファイル: {input_file.name}\n"
                f"検出されたイベント数: {results['segments_count']}\n"
                f"生成されたファイル数: {len(results['split_files'])}\n"
                f"出力ディレクトリ: {results['output_directory']}\n\n"
                f"CSVファイル: {pathlib.Path(results['csv_file']).name if results['csv_file'] else 'なし'}"
            ))
            
        except VideoSplitterError as e:
            self.root.after(0, lambda: messagebox.showerror("動画分割エラー", str(e)))
        except Exception as e:
            logger.error(f"動画分割処理中にエラー: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("エラー", f"動画分割処理中にエラーが発生しました: {str(e)}"))
        finally:
            # UI状態の復帰
            self.root.after(0, lambda: self.execute_button.config(state="normal"))
            self.root.after(0, lambda: self.status_var.set("待機中"))

    def _show_settings(self):
        """設定ダイアログの表示"""
        SettingsDialog(self.root)

    def _open_output_dir(self):
        """出力ディレクトリをエクスプローラーで開く"""
        try:
            # 設定から出力ディレクトリを取得
            config = config_manager.get_config()
            output_dir = config.output.default_dir
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                logger.info(f"出力ディレクトリを作成しました: {output_dir}")
            os.startfile(str(output_dir))
        except Exception as e:
            logger.error(f"出力ディレクトリを開く際にエラーが発生しました: {str(e)}")
            messagebox.showerror("エラー", f"出力ディレクトリを開けませんでした: {str(e)}")

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("設定")
        self.resizable(True, True)  # リサイズ可能に変更
        self.geometry("600x700")    # 高さを800pxに増やす
        
        # ウィンドウを親の上に表示
        self.transient(parent)
        self.lift()
        self.grab_set()  # モーダルダイアログとして設定

        # 設定の読み込み (変更後)
        app_config = config_manager.get_config()
        self.gemini_api_key = app_config.gemini_api_key or ""
        self.transcription_method = app_config.transcription.method
        self.summarization_model = app_config.summarization.model
        self.segment_length = app_config.transcription.segment_length_seconds
        self.enable_speaker_remapping = app_config.transcription.enable_speaker_remapping
        self.output_dir = app_config.output.default_dir
        
        # モデル設定の読み込み
        self.gemini_transcription_model = app_config.models.gemini_transcription
        self.gemini_minutes_model = app_config.models.gemini_minutes
        self.gemini_title_model = app_config.models.gemini_title

        # プロンプトの読み込み
        self.video_segmentation_prompt = prompt_manager.get_prompt("video_segmentation")
        self.default_video_segmentation_prompt = prompt_manager.get_default_prompt("video_segmentation")

        self._create_widgets()
        self._layout_widgets()

    def _create_widgets(self):
        """設定ダイアログのウィジェット作成"""
        # タブコントロールの作成
        self.tab_control = ttk.Notebook(self)
        
        # タブのスタイル設定
        style = ttk.Style()
        style.configure('TNotebook.Tab', padding=[20, 5])  # 左右に20px、上下に5pxのパディングを設定
        
        # 基本設定タブ
        self.basic_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.basic_tab, text="基本設定")
        
        # プロンプト設定タブ
        self.prompt_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.prompt_tab, text="動画分割プロンプト")
        
        # === 基本設定タブのウィジェット ===
        # Gemini API Key設定
        self.gemini_api_key_var = tk.StringVar(value=self.gemini_api_key)
        self.gemini_api_key_frame = ttk.LabelFrame(self.basic_tab, text="Gemini API Key", padding=5)
        self.gemini_api_key_entry = ttk.Entry(self.gemini_api_key_frame, textvariable=self.gemini_api_key_var, show="*")
        
        # 動画解析方式設定
        self.transcription_frame = ttk.LabelFrame(self.basic_tab, text="動画解析方式", padding=5)
        self.transcription_var = tk.StringVar(value=self.transcription_method)
        self.transcription_gemini = ttk.Radiobutton(
            self.transcription_frame,
            text="Gemini方式",
            value="gemini",
            variable=self.transcription_var
        )
        
        # 話者置換処理オプション
        self.enable_speaker_remapping_var = tk.BooleanVar(value=self.enable_speaker_remapping)
        self.enable_speaker_remapping_check = ttk.Checkbutton(
            self.transcription_frame,
            text="話者置換処理を有効にする",
            variable=self.enable_speaker_remapping_var
        )
        self.speaker_remapping_label = ttk.Label(
            self.transcription_frame,
            text="バラバラの話者名が（部分的に）統一されます",
            wraplength=350
        )
        
        # 分割時間設定
        self.segment_length_frame = ttk.LabelFrame(self.basic_tab, text="ファイルを何秒ごとに分割処理するか(推奨:300秒)", padding=5)
        self.segment_length_var = tk.StringVar(value=str(self.segment_length))
        self.segment_length_entry = ttk.Entry(self.segment_length_frame, textvariable=self.segment_length_var)

        # 動画分割モデル設定
        self.summarization_frame = ttk.LabelFrame(self.basic_tab, text="動画分割AI設定", padding=5)
        self.summarization_var = tk.StringVar(value=self.summarization_model)
        self.summarization_gemini = ttk.Radiobutton(
            self.summarization_frame,
            text="Gemini方式",
            value="gemini",
            variable=self.summarization_var
        )

        # 出力ディレクトリ設定
        self.output_dir_var = tk.StringVar(value=self.output_dir)
        self.output_dir_frame = ttk.LabelFrame(self.basic_tab, text="出力ディレクトリ", padding=5)
        self.output_dir_entry = ttk.Entry(self.output_dir_frame, textvariable=self.output_dir_var)
        self.output_dir_button = ttk.Button(
            self.output_dir_frame,
            text="参照",
            command=self._browse_output_dir
        )

        # === モデル設定 ===
        self.models_frame = ttk.LabelFrame(self.basic_tab, text="AIモデル名設定", padding=5)
        
        # 折りたたみ用のフレームとボタン
        self.models_header_frame = ttk.Frame(self.models_frame)
        self.models_header_frame.pack(fill="x", expand=True)
        
        self.models_toggle_button = ttk.Button(
            self.models_header_frame,
            text="▼ 詳細設定を表示",
            command=self._toggle_models_panel
        )
        self.models_toggle_button.pack(anchor="w", padx=5, pady=2)
        
        # モデル設定用のコンテンツフレーム（初期状態は非表示）
        self.models_content_frame = ttk.Frame(self.models_frame)
        self.models_collapsed = True  # 初期状態は折りたたまれている

        # Tkinter StringVars for models
        self.gemini_transcription_model_var = tk.StringVar(value=self.gemini_transcription_model)
        self.gemini_minutes_model_var = tk.StringVar(value=self.gemini_minutes_model)
        self.gemini_title_model_var = tk.StringVar(value=self.gemini_title_model)

        # Create labels and entries for each model
        model_fields = [
            ("Gemini 動画解析:", self.gemini_transcription_model_var),
            ("Gemini 分割処理:", self.gemini_minutes_model_var),
            ("Gemini タイトル生成:", self.gemini_title_model_var),
        ]

        for i, (label_text, var) in enumerate(model_fields):
            label = ttk.Label(self.models_content_frame, text=label_text)
            label.grid(row=i, column=0, padx=5, pady=2, sticky="w")
            entry = ttk.Entry(self.models_content_frame, textvariable=var, width=40)
            entry.grid(row=i, column=1, padx=5, pady=2, sticky="ew")

        self.models_content_frame.columnconfigure(1, weight=1) # Entryが幅を広げるように設定

        # === プロンプト設定タブのウィジェット ===
        # 動画分割プロンプト設定
        self.video_segmentation_prompt_frame = ttk.LabelFrame(self.prompt_tab, text="動画分割プロンプト", padding=5)
        self.video_segmentation_prompt_text = scrolledtext.ScrolledText(
            self.video_segmentation_prompt_frame, 
            wrap=tk.WORD,
            width=60,
            height=20
        )
        self.video_segmentation_prompt_text.insert(tk.END, self.video_segmentation_prompt)
        
        # プロンプトリセットボタン
        self.reset_prompt_button = ttk.Button(
            self.video_segmentation_prompt_frame,
            text="デフォルトに戻す",
            command=self._reset_video_segmentation_prompt
        )

    def _layout_widgets(self):
        """設定ダイアログのウィジェットレイアウト"""
        # タブコントロールをウィンドウいっぱいに広げる
        self.tab_control.pack(fill="both", expand=True, padx=10, pady=10)
        
        # === 基本設定タブのレイアウト ===
        # Gemini API Key
        self.gemini_api_key_frame.pack(fill="x", padx=5, pady=5)
        self.gemini_api_key_entry.pack(fill="x", padx=5, pady=2)
        
        # 動画解析方式
        self.transcription_frame.pack(fill="x", padx=5, pady=5)
        self.transcription_gemini.pack(anchor="w", padx=5, pady=2)
        
        # 話者置換処理
        self.enable_speaker_remapping_check.pack(anchor="w", padx=5, pady=2)
        self.speaker_remapping_label.pack(anchor="w", padx=5, pady=2)
        
        # 分割時間設定
        self.segment_length_frame.pack(fill="x", padx=5, pady=5)
        self.segment_length_entry.pack(fill="x", padx=5, pady=2)

        # 動画分割AI設定
        self.summarization_frame.pack(fill="x", padx=5, pady=5)
        self.summarization_gemini.pack(anchor="w", padx=5, pady=2)

        # 出力ディレクトリ
        self.output_dir_frame.pack(fill="x", padx=5, pady=5)
        self.output_dir_entry.pack(side="left", fill="x", expand=True, padx=5, pady=2)
        self.output_dir_button.pack(side="right", padx=5, pady=2)
        
        # モデル設定
        self.models_frame.pack(fill="x", padx=5, pady=5)
        
        # === プロンプト設定タブのレイアウト ===
        self.video_segmentation_prompt_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.video_segmentation_prompt_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.reset_prompt_button.pack(anchor="e", padx=5, pady=2)
        
        # 保存・キャンセルボタン
        self.button_frame = ttk.Frame(self)
        self.button_frame.pack(fill="x", padx=10, pady=10)
        
        self.save_button = ttk.Button(self.button_frame, text="保存", command=self._save_settings)
        self.save_button.pack(side="right", padx=5)
        
        self.cancel_button = ttk.Button(self.button_frame, text="キャンセル", command=self.destroy)
        self.cancel_button.pack(side="right", padx=5)

    def _reset_video_segmentation_prompt(self):
        """動画分割プロンプトをデフォルトに戻す"""
        if messagebox.askyesno("確認", "動画分割プロンプトをデフォルトに戻しますか？"):
            self.video_segmentation_prompt_text.delete(1.0, tk.END)
            self.video_segmentation_prompt_text.insert(tk.END, self.default_video_segmentation_prompt)

    def _browse_output_dir(self):
        """出力ディレクトリを選択するダイアログを表示"""
        current_dir = self.output_dir_var.get() or os.path.expanduser("~/Documents/議事録")
        if not os.path.exists(current_dir):
            current_dir = os.path.expanduser("~/Documents")
        
        directory = filedialog.askdirectory(
            initialdir=current_dir,
            title="出力ディレクトリの選択"
        )
        
        if directory:  # ユーザーがディレクトリを選択した場合
            self.output_dir_var.set(directory)

    def _toggle_models_panel(self):
        """モデル設定パネルの表示/非表示を切り替える"""
        if self.models_collapsed:
            # 折りたたみを展開
            self.models_content_frame.pack(fill="both", expand=True, padx=5, pady=5)
            self.models_toggle_button.config(text="▲ 詳細設定を隠す")
            self.models_collapsed = False
        else:
            # 折りたたむ
            self.models_content_frame.pack_forget()
            self.models_toggle_button.config(text="▼ 詳細設定を表示")
            self.models_collapsed = True 

    def _save_settings(self):
        """設定を保存する"""
        try:
            # 分割秒数の検証
            try:
                segment_length = int(self.segment_length_var.get())
                if segment_length <= 0:
                    messagebox.showerror("エラー", "分割秒数は正の整数を入力してください")
                    return
            except ValueError:
                messagebox.showerror("エラー", "分割秒数は整数を入力してください")
                return

            # 基本設定の保存
            config_data = {
                "gemini_api_key": self.gemini_api_key_var.get(),
                "output": {
                    "default_dir": self.output_dir_var.get()
                },
                "transcription": {
                    "method": self.transcription_var.get(),
                    "segment_length_seconds": segment_length,
                    "enable_speaker_remapping": self.enable_speaker_remapping_var.get()
                },
                "summarization": {
                    "model": self.summarization_var.get()
                },
                "models": {
                    "gemini_transcription": self.gemini_transcription_model_var.get(),
                    "gemini_minutes": self.gemini_minutes_model_var.get(),
                    "gemini_title": self.gemini_title_model_var.get(),
                }
            }

            # 設定の更新と保存
            config_manager.update_config(config_data)
            
            # プロンプト設定の保存
            video_segmentation_prompt = self.video_segmentation_prompt_text.get("1.0", tk.END).strip()
            if not prompt_manager.save_custom_prompt("video_segmentation", video_segmentation_prompt):
                 messagebox.showerror("エラー", "動画分割プロンプトの保存に失敗しました")
                 return # 保存失敗時はダイアログを閉じない
            
            # ダイアログを閉じる
            messagebox.showinfo("設定保存", "設定を保存しました")
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("エラー", f"設定の保存中にエラーが発生しました: {str(e)}") 