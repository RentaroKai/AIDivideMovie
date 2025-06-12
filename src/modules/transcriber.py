import os
import logging
import json
from pathlib import Path
from src.services.gemini_transcription import GeminiTranscriptionService, TranscriptionError

logger = logging.getLogger(__name__)

class GeminiTranscriber:
    def __init__(self):
        """
        Gemini APIを使用した文字起こしクラスの初期化
        """
        logger.info("GeminiTranscriberを初期化中...")
        self.service = GeminiTranscriptionService()
        logger.info("GeminiTranscriberの初期化が完了しました")

    def transcribe_audio(self, file_path):
        """
        音声ファイルまたは動画ファイルを文字起こしする
        Args:
            file_path (str): 音声または動画ファイルのパス
        Returns:
            dict: 文字起こし結果の辞書（含む："conversations"リスト）
        """
        try:
            logger.info(f"文字起こしを開始: {file_path}")
            
            # 拡張子を確認して、動画ファイルかどうかを判定
            file_extension = Path(file_path).suffix.lower()
            is_video = file_extension in ['.mp4', '.avi', '.mov', '.mkv', '.webm']
            
            logger.info(f"ファイルタイプ: {'動画' if is_video else '音声'}, 拡張子: {file_extension}")
            
            # GeminiTranscriptionServiceを使用して文字起こし
            # process_mediaはprocess_audioを置き換えるメソッド（内部で動画か音声かを判定）
            result = self.service.process_media(Path(file_path), is_video=is_video)
            
            # formatted_textを取得
            response_text = result.get("formatted_text", "")
            logger.debug(f"文字起こし結果の長さ: {len(response_text)} 文字")
            
            # GeminiはJSON風のテキストを返すが、単なるテキストとして扱う
            # ここで字句解析（パース）はせずにオブジェクトを構築
            # 下流の処理では通常のpythonオブジェクトとして扱える
            return {
                "conversations": [
                    {
                        "speaker": "話者",
                        "utterance": response_text
                    }
                ]
            }
            
        except Exception as e:
            logger.error(f"文字起こし処理でエラーが発生: {str(e)}", exc_info=True)
            raise TranscriptionError(f"文字起こし処理に失敗: {str(e)}")

    def save_transcription(self, transcription, output_file):
        """
        文字起こし結果をテキストファイルとして保存
        Args:
            transcription (str): 文字起こし結果のテキスト
            output_file (str): 出力ファイルパス
        """
        try:
            logger.info(f"文字起こし結果を保存: {output_file}")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(transcription)
            logger.info(f"文字起こし結果を保存しました: {output_file}")
        except Exception as e:
            logger.error(f"文字起こし結果の保存中にエラーが発生: {str(e)}", exc_info=True)
            raise 