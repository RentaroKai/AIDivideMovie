import logging
from pathlib import Path
from typing import Dict, Any
# from .audio import AudioProcessor, AudioProcessingError
from .transcription import TranscriptionService
from .csv_converter import CSVConverterService
from .minutes import MinutesService
from .format_converter import convert_file, cleanup_file, FormatConversionError
from .meeting_title_service import MeetingTitleService
from .speaker_remapper import create_speaker_remapper
from src.utils.config import config_manager
from src.utils.video_compressor import VideoCompressor, VideoCompressionError

logger = logging.getLogger(__name__)

def process_audio_file(input_file: Path, modes: dict) -> dict:
    """メディアファイル（動画/音声）の処理を実行"""
    results = {}
    
    logger.info(f"処理開始 - 入力ファイル: {input_file}")
    logger.info(f"モード設定: {modes}")
    
    # 追加: 変換フラグおよび変換後ファイル保持用変数の初期化
    conversion_performed = False
    converted_file = None
    compression_performed = False
    compressed_file = None

    try:
        # 新機能: 動画圧縮処理
        # 動画のサイズが大きい場合に自動的に圧縮を適用する
        try:
            logger.info("ファイルサイズをチェックし、必要に応じて動画圧縮を適用します")
            video_compressor = VideoCompressor()  # デフォルト設定で初期化（1GB超で圧縮）
            input_file_path = Path(input_file)
            processed_file, was_compressed = video_compressor.compress_if_needed(input_file_path)
            
            if was_compressed:
                logger.info(f"動画が圧縮されました。圧縮後のファイルを使用します: {processed_file}")
                input_file = processed_file
                compression_performed = True
                compressed_file = processed_file
            else:
                logger.info("動画圧縮は不要または適用されませんでした。元のファイルを使用します。")
        except VideoCompressionError as e:
            logger.error(f"動画圧縮中にエラーが発生しました: {str(e)}")
            logger.warning("圧縮処理をスキップして元のファイルを使用します")
        except Exception as e:
            logger.error(f"予期しない動画圧縮エラー: {str(e)}", exc_info=True)
            logger.warning("圧縮処理をスキップして元のファイルを使用します")

        # 追加: ファイル形式の判定・変換処理
        original_path = str(input_file)
        try:
            converted = convert_file(original_path)
            if converted != original_path:
                conversion_performed = True
                converted_file = Path(converted)
                logger.info(f"変換が実施されました。変換後のファイルを使用します: {converted_file}")
                input_file = converted_file
            else:
                logger.info("ファイル形式は既に対応済みのため変換は不要です。")
        except FormatConversionError as e:
            logger.error(f"ファイル形式の変換に失敗しました: {str(e)}")
            raise RuntimeError(f"ファイル形式の変換に失敗しました: {str(e)}")

        # 音声抽出処理を削除し、直接メディアファイルを転送
        # 既に適切な形式に変換済みなので、そのまま利用
        
        try:
            # 書き起こし処理（必須）
            if modes["transcribe"]:
                logger.info("書き起こし処理を開始")
                transcription_service = TranscriptionService()
                # 変換されたメディアファイルまたは元のメディアファイルを直接転送
                transcription_result = transcription_service.process_audio(input_file)
                results["transcription"] = transcription_result
                
                # 会議タイトル生成処理を追加
                try:
                    logger.info("会議タイトル生成処理を開始")
                    # タイトル出力ディレクトリの確認と作成
                    title_output_dir = Path("output/title")
                    if not title_output_dir.exists():
                        title_output_dir.mkdir(parents=True, exist_ok=True)
                        logger.info(f"タイトル出力ディレクトリを作成しました: {title_output_dir}")

                    title_service = MeetingTitleService()
                    transcript_file_path = transcription_result.get("formatted_file")
                    if transcript_file_path:
                        title_file_path = title_service.process_transcript_and_generate_title(str(transcript_file_path))
                        results["meeting_title"] = {"file_path": title_file_path}
                        logger.info(f"会議タイトル生成完了: {title_file_path}")
                    else:
                        logger.warning("書き起こしファイルのパスが見つかりません")
                except Exception as e:
                    logger.error(f"会議タイトル生成中にエラーが発生: {str(e)}")
                    results["meeting_title"] = {"error": str(e)}
                
                # 追加: スピーカーリマップ処理
                try:
                    # 話者置換処理の設定を取得
                    enable_speaker_remapping = config_manager.get_config().transcription.enable_speaker_remapping
                    
                    if enable_speaker_remapping:
                        logger.info("スピーカーリマップ処理を開始")
                        speaker_remapper = create_speaker_remapper()
                        transcript_file_path = transcription_result.get("formatted_file")
                        if transcript_file_path:
                            remapped_file_path = speaker_remapper.process_transcript(transcript_file_path)
                            # リマップ後のファイルを以降の処理で使用するように設定
                            transcription_result["formatted_file"] = remapped_file_path
                            results["speaker_remap"] = {"file_path": remapped_file_path}
                            logger.info(f"スピーカーリマップ処理完了: {remapped_file_path}")
                        else:
                            logger.warning("書き起こしファイルのパスが見つかりません")
                    else:
                        logger.info("話者置換処理はオプションで無効化されているためスキップします")
                        results["speaker_remap"] = {"status": "skipped", "reason": "disabled_by_config"}
                except Exception as e:
                    logger.error(f"スピーカーリマップ処理中にエラーが発生: {str(e)}")
                    results["speaker_remap"] = {"error": str(e)}
                
                # CSV変換
                logger.info("CSV変換を開始")
                csv_converter = CSVConverterService()
                csv_file = csv_converter.convert_to_csv(transcription_result["formatted_file"])
                results["csv"] = csv_file
            
            # 議事録生成
            if modes["minutes"]:
                logger.info("議事録生成を開始")
                minutes_service = MinutesService()
                minutes_result = minutes_service.generate_minutes(transcription_result["formatted_file"])
                # 戻り値のキーを適切に取り扱う
                results["minutes"] = minutes_result.get("file_path") or minutes_result.get("minutes_file")
                if not results["minutes"]:
                    logger.error("議事録ファイルのパスが取得できませんでした")
                    raise ValueError("議事録ファイルのパスが取得できませんでした")
            
            # 反省点抽出
            if modes["reflection"]:
                logger.info("反省点抽出を開始")
                minutes_service = MinutesService()
                
                # 議事録ファイルの内容を読み込む
                with open(results["minutes"], "r", encoding="utf-8") as f:
                    minutes_content = f.read()
                
                # 議事録から反省点を抽出
                reflection_path = minutes_service.extract_reflection_points(minutes_content)
                results["reflection"] = reflection_path
            
            # 成功結果を返す
            results["success"] = True
            return results
            
        except Exception as e:
            # 処理中のエラー
            logger.error(f"処理中にエラーが発生: {str(e)}")
            results["success"] = False
            results["error"] = str(e)
            return results
            
    except Exception as e:
        # 前処理中のエラー
        logger.error(f"メディア前処理中にエラーが発生: {str(e)}")
        results["success"] = False
        results["error"] = str(e)
        return results
    finally:
        # 一時ファイルのクリーンアップ
        if conversion_performed and converted_file and converted_file.exists():
            try:
                cleanup_file(str(converted_file))
                logger.info(f"変換一時ファイルを削除しました: {converted_file}")
            except Exception as e:
                logger.warning(f"変換一時ファイルの削除に失敗: {str(e)}")
        
        # 圧縮された一時ファイルのクリーンアップ
        if compression_performed and compressed_file and compressed_file.exists():
            try:
                compressed_file.unlink()
                logger.info(f"圧縮一時ファイルを削除しました: {compressed_file}")
            except Exception as e:
                logger.warning(f"圧縮一時ファイルの削除に失敗: {str(e)}") 