import logging
from typing import Optional
from .base_title_generator import BaseTitleGenerator
from .gemini_title_generator import GeminiTitleGenerator

logger = logging.getLogger(__name__)

class TitleGeneratorFactoryError(Exception):
    """タイトルジェネレーターファクトリーのエラーを扱うカスタム例外クラス"""
    pass

class TitleGeneratorFactory:
    """タイトルジェネレーターのファクトリークラス"""
    
    @staticmethod
    def create_generator(transcription_method: str) -> BaseTitleGenerator:
        """
        書き起こし方式に応じたタイトルジェネレーターを生成する

        Args:
            transcription_method (str): 書き起こし方式（現在は"gemini"のみサポート）

        Returns:
            BaseTitleGenerator: タイトルジェネレーターのインスタンス

        Raises:
            TitleGeneratorFactoryError: サポートされていない書き起こし方式が指定された場合
        """
        try:
            logger.info(f"タイトルジェネレーターを作成: 書き起こし方式 = {transcription_method}")
            
            if transcription_method == "gemini":
                return GeminiTitleGenerator()
            else:
                # gemini 以外の方式はサポートされていないためエラーとする
                logger.warning(f"サポートされていない書き起こし方式です: {transcription_method}。Gemini方式のみサポートされています。")
                raise TitleGeneratorFactoryError(f"サポートされていない書き起こし方式です: {transcription_method}。Gemini方式を使用してください。")
                
        except Exception as e:
            error_msg = f"タイトルジェネレーターの作成に失敗: {str(e)}"
            logger.error(error_msg)
            raise TitleGeneratorFactoryError(error_msg) 