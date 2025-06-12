import os
import logging
import subprocess
from pathlib import Path
import tempfile
import uuid
from typing import Tuple

from src.utils.ffmpeg_handler import get_ffmpeg_path, get_ffprobe_path

logger = logging.getLogger(__name__)

# 定数定義
GB_IN_BYTES = 1024 * 1024 * 1024  # 1GB = 1024³ bytes
MB_IN_BYTES = 1024 * 1024  # 1MB = 1024² bytes
DEFAULT_SIZE_THRESHOLD = 100 * MB_IN_BYTES  # 200MB
DEFAULT_TARGET_WIDTH = 1280  # 長辺の最大サイズ
DEFAULT_CRF = 28  # 圧縮品質（値が大きいほど低品質・高圧縮）
DEFAULT_AUDIO_BITRATE = "128k"  # 音声ビットレート


class VideoCompressionError(Exception):
    """動画圧縮関連のエラーを扱うカスタム例外クラス"""
    pass


class VideoCompressor:
    def __init__(self, 
                 size_threshold_bytes: int = DEFAULT_SIZE_THRESHOLD,
                 target_width: int = DEFAULT_TARGET_WIDTH,
                 crf: int = DEFAULT_CRF,
                 audio_bitrate: str = DEFAULT_AUDIO_BITRATE):
        """
        動画圧縮クラスの初期化
        
        Args:
            size_threshold_bytes: 圧縮を行うサイズのしきい値（バイト単位）
            target_width: 圧縮後の動画の長辺の最大サイズ（ピクセル）
            crf: 圧縮品質（値が大きいほど低品質・高圧縮、一般的に18〜28が適切）
            audio_bitrate: 音声ビットレート
        """
        self.size_threshold = size_threshold_bytes
        self.target_width = target_width
        self.crf = crf
        self.audio_bitrate = audio_bitrate
        
        # 一時ディレクトリの設定
        self.temp_dir = Path(tempfile.gettempdir()) / "GiJiRoKu_video_temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # FFmpegのパスを取得
        self.ffmpeg_path = get_ffmpeg_path()
        self.ffprobe_path = get_ffprobe_path()
        
        if not self.ffmpeg_path:
            raise VideoCompressionError("FFmpegが見つかりません。動画圧縮は実行できません。")
        
        logger.info(f"VideoCompressorを初期化しました (しきい値: {self.size_threshold/GB_IN_BYTES:.2f}GB, "
                   f"幅: {self.target_width}px, CRF: {self.crf}, 音声: {self.audio_bitrate})")

    def compress_if_needed(self, input_file: Path) -> Tuple[Path, bool]:
        """
        動画ファイルのサイズを確認し、必要に応じて圧縮する
        
        Args:
            input_file: 入力動画ファイルのパス
            
        Returns:
            Tuple[Path, bool]: (処理後のファイルパス, 圧縮が行われたかどうか)
        """
        # ファイルの存在確認
        if not input_file.exists():
            logger.error(f"入力ファイルが存在しません: {input_file}")
            raise FileNotFoundError(f"入力ファイルが存在しません: {input_file}")
        
        # ファイルサイズの取得
        file_size = input_file.stat().st_size
        logger.info(f"入力ファイルのサイズ: {file_size/GB_IN_BYTES:.2f}GB ({file_size:,} bytes)")
        
        # サイズがしきい値以下の場合、圧縮せずに元のファイルを返す
        if file_size <= self.size_threshold:
            logger.info(f"ファイルサイズがしきい値({self.size_threshold/GB_IN_BYTES:.2f}GB)以下のため圧縮は不要です")
            return input_file, False
        
        # 圧縮処理を実行
        try:
            compressed_file = self._compress_video(input_file)
            
            # 圧縮後のファイルサイズを取得
            compressed_size = compressed_file.stat().st_size
            logger.info(f"圧縮後のファイルサイズ: {compressed_size/GB_IN_BYTES:.2f}GB ({compressed_size:,} bytes)")
            
            # 圧縮率を計算
            compression_ratio = (1 - compressed_size/file_size) * 100
            logger.info(f"圧縮率: {compression_ratio:.1f}%")
            
            # 圧縮後のサイズが元のサイズより大きい場合、元のファイルを使用
            if compressed_size >= file_size:
                logger.warning("圧縮後のサイズが元のサイズより大きくなりました。元のファイルを使用します。")
                compressed_file.unlink()
                return input_file, False
            
            return compressed_file, True
            
        except Exception as e:
            logger.error(f"動画圧縮処理中にエラーが発生しました: {str(e)}", exc_info=True)
            raise VideoCompressionError(f"動画圧縮処理中にエラーが発生しました: {str(e)}")

    def _compress_video(self, input_file: Path) -> Path:
        """
        FFmpegを使用して動画を圧縮する
        
        Args:
            input_file: 入力動画ファイルのパス
            
        Returns:
            Path: 圧縮された動画ファイルのパス
        """
        # 出力ファイル名の生成
        output_file = self.temp_dir / f"compressed_{uuid.uuid4().hex}{input_file.suffix}"
        logger.info(f"圧縮動画ファイルを作成: {output_file}")
        
        # FFmpegコマンドの構築
        cmd = [
            str(self.ffmpeg_path),
            "-y",  # 既存ファイルを上書き
            "-i", str(input_file),
            "-vf", f"scale='min({self.target_width},iw)':-2",  # アスペクト比を維持したまま長辺を指定サイズに
            "-c:v", "libx264",  # H.264コーデック
            "-preset", "veryfast",  # エンコード速度設定
            "-crf", str(self.crf),  # 品質設定
            "-c:a", "aac",  # 音声コーデック
            "-b:a", self.audio_bitrate,  # 音声ビットレート
            "-movflags", "+faststart",  # Web再生用の最適化
            str(output_file)
        ]
        
        logger.debug(f"FFmpeg圧縮コマンド: {' '.join(cmd)}")
        
        # FFmpegの実行
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.stderr:
                logger.debug(f"FFmpeg stderr出力: {result.stderr}")
                
            if not output_file.exists():
                raise VideoCompressionError(f"FFmpeg処理後に出力ファイルが見つかりません: {output_file}")
                
            return output_file
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpegエラー: {e.stderr}")
            logger.error(f"FFmpegコマンド: {e.cmd}")
            logger.error(f"FFmpeg終了コード: {e.returncode}")
            raise VideoCompressionError(f"FFmpeg処理に失敗しました: {e.stderr}") 