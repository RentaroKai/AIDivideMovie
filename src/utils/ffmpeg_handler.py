"""
FFMPEGハンドラーモジュール

FFMPEG関連の機能を一元化して管理するモジュール。
- バイナリの検出
- パスの解決
- 環境変数の設定
- pydubの設定

Date: 2023-03-07
"""

import os
import sys
import logging
import shutil
from pathlib import Path
import subprocess
import re

logger = logging.getLogger(__name__)

def get_base_path():
    """
    実行環境に合わせたベースパスを返す。
    - PyInstallerでビルドされた実行環境の場合は sys._MEIPASS を返す
    - 通常の Python 実行の場合は、プロジェクトルートを返す
    """
    if getattr(sys, 'frozen', False):
        # PyInstallerによる実行環境
        base_path = sys._MEIPASS
        logger.debug(f"EXE実行モード: base_path = {base_path}")
    else:
        # 通常のPython実行環境
        base_path = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        logger.debug(f"Python実行モード: base_path = {base_path}")
    return base_path

def get_ffmpeg_path():
    """
    FFmpeg実行ファイルのパスを返す。
    複数の可能性のあるパスを順番に探索し、最初に見つかったパスを返す。
    """
    base_path = get_base_path()
    
    # 最初に探索する標準パス
    ffmpeg_path = os.path.join(base_path, "resources", "ffmpeg", "ffmpeg.exe")
    
    if os.path.exists(ffmpeg_path):
        logger.debug(f"FFmpegパスが見つかりました: {ffmpeg_path}")
        return ffmpeg_path
    
    # 標準パスに見つからない場合は、他の可能性のあるパスを探索
    logger.warning(f"標準パスにFFmpegが見つかりませんでした: {ffmpeg_path}")
    possible_paths = [
        os.path.join(base_path, "ffmpeg.exe"),  # ルートディレクトリ
        os.path.join(os.path.dirname(base_path), "resources", "ffmpeg", "ffmpeg.exe"),  # 親ディレクトリのリソース
        shutil.which("ffmpeg")  # システムパスに設定されているffmpeg
    ]
    
    for path in possible_paths:
        if path and os.path.exists(path):
            logger.info(f"代替のFFmpegパスが見つかりました: {path}")
            return path
    
    logger.error("FFmpegが見つかりませんでした")
    return None

def get_ffprobe_path():
    """
    ffprobe実行ファイルのパスを返す。
    複数の可能性のあるパスを順番に探索し、最初に見つかったパスを返す。
    """
    base_path = get_base_path()
    
    # 最初に探索する標準パス
    ffprobe_path = os.path.join(base_path, "resources", "ffmpeg", "ffprobe.exe")
    
    if os.path.exists(ffprobe_path):
        logger.debug(f"ffprobeパスが見つかりました: {ffprobe_path}")
        return ffprobe_path
    
    # 標準パスに見つからない場合は、他の可能性のあるパスを探索
    logger.warning(f"標準パスにffprobeが見つかりませんでした: {ffprobe_path}")
    possible_paths = [
        os.path.join(base_path, "ffprobe.exe"),  # ルートディレクトリ
        os.path.join(os.path.dirname(base_path), "resources", "ffmpeg", "ffprobe.exe"),  # 親ディレクトリのリソース
        shutil.which("ffprobe")  # システムパスに設定されているffprobe
    ]
    
    for path in possible_paths:
        if path and os.path.exists(path):
            logger.info(f"代替のffprobeパスが見つかりました: {path}")
            return path
    
    logger.error("ffprobeが見つかりませんでした")
    return None

def setup_ffmpeg():
    """
    FFmpegの環境設定を行う。
    - FFmpegとffprobeのパスを取得
    - 環境変数を設定（PATH, FFMPEG_BINARY, FFPROBE_BINARY）
    - pydubの設定を更新

    Returns:
        tuple: (ffmpeg_path, ffprobe_path) - 設定されたパス
    """
    try:
        # FFmpegのパスを取得
        ffmpeg_path = get_ffmpeg_path()
        if not ffmpeg_path:
            raise FileNotFoundError("FFmpegが見つかりませんでした。アプリケーションが正常に動作しない可能性があります。")
        
        # ffprobeのパスを取得
        ffprobe_path = get_ffprobe_path()
        
        # FFmpegのディレクトリをPATHに追加
        ffmpeg_dir = os.path.dirname(ffmpeg_path)
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        logger.debug(f"PATHを更新しました: {ffmpeg_dir} を追加")
        
        # pydubのconverter設定
        try:
            from pydub import AudioSegment
            AudioSegment.converter = ffmpeg_path
            if ffprobe_path:
                AudioSegment.ffprobe = ffprobe_path
            logger.debug(f"pydub設定を更新しました: converter={ffmpeg_path}, ffprobe={ffprobe_path}")
        except ImportError:
            logger.warning("pydubのインポートに失敗しました。AudioSegment設定はスキップします。")
        
        # 環境変数の設定
        os.environ["FFMPEG_BINARY"] = ffmpeg_path
        if ffprobe_path:
            os.environ["FFPROBE_BINARY"] = ffprobe_path
        
        logger.info(f"FFmpeg設定が完了しました: ffmpeg={ffmpeg_path}, ffprobe={ffprobe_path}")
        return ffmpeg_path, ffprobe_path
        
    except Exception as e:
        logger.error(f"FFmpeg設定中にエラーが発生しました: {str(e)}", exc_info=True)
        raise

def extract_audio(input_file, output_file):
    """
    動画ファイルから音声を抽出する（非推奨）
    
    警告: この関数は非推奨です。代わりに split_media_fixed_duration を使用してください。
    
    Args:
        input_file (str): 入力動画ファイルのパス
        output_file (str): 出力音声ファイルのパス
        
    Returns:
        bool: 成功した場合はTrue
    """
    logger.warning("extract_audio関数は非推奨です。代わりにsplit_media_fixed_durationを使用してください。")
    
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        logger.error("FFmpegが見つかりません。音声抽出は実行できません。")
        return False
    
    try:
        cmd = [
            ffmpeg_path,
            "-i", input_file,
            "-vn",  # 映像を除去
            "-acodec", "copy",  # 音声コーデックをそのままコピー
            output_file
        ]
        
        logger.debug(f"FFmpeg抽出コマンド: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result.stderr:
            logger.debug(f"FFmpeg stderr出力: {result.stderr}")
            
        logger.info(f"音声抽出が完了しました: {output_file}")
        return True
    
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpegエラー: {e.stderr}")
        logger.error(f"FFmpegコマンド: {e.cmd}")
        logger.error(f"FFmpeg終了コード: {e.returncode}")
        return False
    except Exception as e:
        logger.error(f"音声抽出エラー: {str(e)}")
        return False

def get_media_duration(input_file):
    """
    メディアファイル（動画/音声）の長さを秒単位で取得する
    
    Args:
        input_file (str): 入力メディアファイルのパス
        
    Returns:
        float: メディアの長さ（秒）、エラーの場合は-1
    """
    ffprobe_path = get_ffprobe_path()
    if not ffprobe_path:
        logger.error("ffprobeが見つかりません。メディア長の取得は実行できません。")
        return -1
    
    try:
        cmd = [
            ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            input_file
        ]
        
        logger.debug(f"ffprobeコマンド: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        duration = float(result.stdout.strip())
        logger.debug(f"メディア長取得: {duration}秒")
        return duration
    
    except subprocess.CalledProcessError as e:
        logger.error(f"ffprobeエラー: {e.stderr}")
        return -1
    except Exception as e:
        logger.error(f"メディア長取得エラー: {str(e)}")
        return -1

def split_media_fixed_duration(input_file, output_dir, segment_duration_sec, file_extension=None):
    """
    メディアファイル（動画/音声）を固定秒数で分割する
    
    Args:
        input_file (str): 入力メディアファイルのパス
        output_dir (str): 出力ディレクトリのパス
        segment_duration_sec (int): 分割する長さ（秒）
        file_extension (str, optional): 出力ファイルの拡張子。指定しない場合は入力ファイルと同じ拡張子を使用
        
    Returns:
        list: 分割されたメディアファイルのパスのリスト
    """
    print ("通ったよ")
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        logger.error("FFmpegが見つかりません。メディア分割は実行できません。")
        raise FileNotFoundError("FFmpegが見つかりません。メディア分割は実行できません。")
    
    # 入力ファイルの絶対パスを取得
    input_path = Path(input_file).resolve()
    if not input_path.exists():
        logger.error(f"入力ファイルが存在しません: {input_path}")
        raise FileNotFoundError(f"入力ファイルが存在しません: {input_path}")
    
    # 出力ディレクトリの準備
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 出力ファイルの拡張子を決定
    if not file_extension:
        file_extension = input_path.suffix
    else:
        if not file_extension.startswith('.'):
            file_extension = '.' + file_extension
    
    # メディアの長さを取得
    duration = get_media_duration(str(input_path))
    if duration <= 0:
        logger.error("メディアの長さを取得できませんでした。")
        raise ValueError("メディアの長さを取得できませんでした。")
    
    logger.info(f"メディア分割を開始: {input_path}")
    logger.info(f"総再生時間: {duration:.2f}秒")
    logger.info(f"指定セグメント長: {segment_duration_sec}秒")
    
    # 分割するファイル名の接頭辞（元ファイル名を使用）
    prefix = input_path.stem
    
    # セグメント数を計算
    num_segments = int(duration / segment_duration_sec) + (1 if duration % segment_duration_sec > 0 else 0)
    logger.info(f"予想セグメント数: {num_segments}")
    
    # 分割されたファイルのパスを保存するリスト
    segment_files = []
    
    try:
        # セグメントフォーマットの指定。Windows対応のためにパスの区切り文字に注意
        segment_format = str(output_path / f"{prefix}_segment_%03d{file_extension}")
        
        # FFmpegコマンドの構築 - キーフレームに依存せず正確に分割するオプションを追加
        cmd = [
            ffmpeg_path,
            "-i", str(input_path),
            "-f", "segment",
            "-segment_time", str(segment_duration_sec),
            "-reset_timestamps", "1",
            "-map", "0",  # すべてのストリームをマップ
            "-c", "copy",  # ストリームをそのままコピー
            "-force_key_frames", f"expr:gte(t,n_forced*{segment_duration_sec})",  # 指定した間隔で強制的にキーフレームを挿入
            "-break_non_keyframes", "1",  # キーフレームでなくても分割を許可
            "-segment_time_delta", "0.05",  # 許容誤差を少なめに設定（0.05秒）
            segment_format
        ]
        
        logger.debug(f"FFmpeg分割コマンド: {' '.join(cmd)}")
        
        # FFmpegを実行
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result.stderr:
            logger.debug(f"FFmpeg stderr出力: {result.stderr}")
        
        # 生成されたファイルを確認
        pattern = re.escape(prefix) + r"_segment_\d{3}" + re.escape(file_extension)
        for file in output_path.glob(f"{prefix}_segment_*{file_extension}"):
            if re.search(pattern, file.name):
                segment_files.append(str(file))
                logger.debug(f"セグメントファイルを検出: {file}")
        
        segment_files.sort()  # ファイル名でソート
        
        logger.info(f"メディア分割が完了しました。合計 {len(segment_files)} 個のセグメントを作成")
        for i, segment_file in enumerate(segment_files, 1):
            logger.info(f"セグメント {i}: {segment_file}")
        
        # 予期しないセグメント数の場合は警告
        if len(segment_files) != num_segments:
            logger.warning(f"予想セグメント数（{num_segments}）と実際のセグメント数（{len(segment_files)}）が一致しません。")
        
        return segment_files
    
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpegエラー: {e.stderr}")
        logger.error(f"FFmpegコマンド: {e.cmd}")
        logger.error(f"FFmpeg終了コード: {e.returncode}")
        raise RuntimeError(f"メディア分割に失敗しました: {e.stderr}")
    except Exception as e:
        logger.error(f"メディア分割エラー: {str(e)}")
        raise RuntimeError(f"メディア分割に失敗しました: {str(e)}")