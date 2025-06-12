import logging
import os
import csv
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import subprocess

from ..utils.new_gemini_api import GeminiAPI, MediaType, GeminiAPIError
from ..utils.prompt_manager import prompt_manager
from ..utils.config import config_manager
from ..utils.ffmpeg_handler import setup_ffmpeg

logger = logging.getLogger(__name__)

class VideoSplitterError(Exception):
    """動画分割処理中のエラーを表すカスタム例外"""
    pass

class VideoSplitter:
    """動画分割サービス"""
    
    def __init__(self):
        """動画分割サービスを初期化"""
        self.gemini_api = GeminiAPI()
        self.config = config_manager.get_config()
        
        # FFmpegの設定
        self.ffmpeg_path, self.ffprobe_path = setup_ffmpeg()
        logger.info(f"FFmpeg設定: {self.ffmpeg_path}")
        
    def split_video(self, input_video_path: str, output_dir: str = None) -> Dict[str, any]:
        """
        動画を分割する
        
        Args:
            input_video_path (str): 入力動画ファイルのパス
            output_dir (str, optional): 出力ディレクトリ。指定されない場合は設定から取得
            
        Returns:
            Dict[str, any]: 分割結果の詳細
            
        Raises:
            VideoSplitterError: 分割処理に失敗した場合
        """
        try:
            input_path = Path(input_video_path)
            if not input_path.exists():
                raise VideoSplitterError(f"入力ファイルが見つかりません: {input_video_path}")
            
            # 出力ディレクトリの設定
            if output_dir is None:
                output_dir = self.config.output.default_dir
            
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"動画分割を開始: {input_path.name}")
            
            # Step 1: Gemini APIで動画解析してイベントIDとタイムスタンプを取得
            logger.info("Step 1: 動画解析中...")
            event_segments = self._analyze_video(str(input_path))
            
            if not event_segments:
                raise VideoSplitterError("動画からイベントIDが検出されませんでした")
            
            logger.info(f"検出されたイベント数: {len(event_segments)}")
            
            # Step 2: FFmpegで動画を分割
            logger.info("Step 2: 動画分割中...")
            split_files = self._split_video_with_ffmpeg(
                str(input_path), 
                event_segments, 
                str(output_path)
            )
            
            # Step 3: CSVファイルに結果を保存
            csv_file = self._save_segments_to_csv(event_segments, str(output_path))
            
            result = {
                "input_file": str(input_path),
                "output_directory": str(output_path),
                "segments_count": len(event_segments),
                "split_files": split_files,
                "csv_file": csv_file,
                "segments": event_segments
            }
            
            logger.info(f"動画分割が完了しました: {len(split_files)}個のファイルを生成")
            return result
            
        except Exception as e:
            logger.error(f"動画分割中にエラーが発生しました: {str(e)}")
            raise VideoSplitterError(f"動画分割処理に失敗しました: {str(e)}")
    
    def _analyze_video(self, video_path: str) -> List[Dict[str, str]]:
        """
        Gemini APIを使用して動画を解析し、イベントIDとタイムスタンプを抽出
        
        Args:
            video_path (str): 動画ファイルのパス
            
        Returns:
            List[Dict[str, str]]: イベントセグメントのリスト
        """
        try:
            # プロンプトを取得
            prompt = prompt_manager.get_prompt("video_segmentation")
            if not prompt:
                raise VideoSplitterError("動画分割プロンプトが見つかりません")
            
            logger.info("Gemini APIで動画解析を開始...")
            
            # Gemini APIで動画を解析
            response = self._analyze_video_with_custom_prompt(video_path, prompt)
            
            logger.debug(f"Gemini API応答: {response[:200]}...")
            
            # 応答からCSV形式のデータを抽出
            segments = self._parse_csv_response(response)
            
            return segments
            
        except GeminiAPIError as e:
            logger.error(f"Gemini API処理中にエラー: {str(e)}")
            raise VideoSplitterError(f"動画解析に失敗しました: {str(e)}")
        except Exception as e:
            logger.error(f"動画解析中に予期せぬエラー: {str(e)}")
            raise VideoSplitterError(f"動画解析中にエラーが発生しました: {str(e)}")
    
    def _parse_csv_response(self, response: str) -> List[Dict[str, str]]:
        """
        Gemini APIからの応答をパースしてCSVデータを抽出
        
        Args:
            response (str): Gemini APIからの応答テキスト
            
        Returns:
            List[Dict[str, str]]: パースされたセグメントデータ
        """
        segments = []
        
        try:
            # CSV形式のブロックを探す
            csv_pattern = r'```csv\s*\n(.*?)\n```'
            csv_match = re.search(csv_pattern, response, re.DOTALL)
            
            if csv_match:
                csv_content = csv_match.group(1).strip()
            else:
                # CSV ブロックが見つからない場合は、レスポンス全体からCSV形式を探す
                lines = response.strip().split('\n')
                csv_lines = []
                in_csv = False
                
                for line in lines:
                    line = line.strip()
                    if 'event_id,start_time,end_time' in line.lower():
                        in_csv = True
                        csv_lines.append(line)
                    elif in_csv and ',' in line and len(line.split(',')) >= 3:
                        csv_lines.append(line)
                    elif in_csv and line == '':
                        continue
                    elif in_csv:
                        break
                
                csv_content = '\n'.join(csv_lines)
            
            if not csv_content:
                logger.warning("CSVデータが見つかりませんでした")
                return segments
            
            # CSVをパース
            lines = csv_content.strip().split('\n')
            if len(lines) < 2:  # ヘッダー + 最低1行のデータ
                logger.warning("有効なCSVデータが見つかりませんでした")
                return segments
            
            # ヘッダーをスキップしてデータを処理
            for line in lines[1:]:
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    event_id = parts[0].strip()
                    start_time = parts[1].strip()
                    end_time = parts[2].strip()
                    
                    if event_id and start_time and end_time:
                        segments.append({
                            'event_id': event_id,
                            'start_time': start_time,
                            'end_time': end_time
                        })
            
            logger.info(f"パースされたセグメント数: {len(segments)}")
            return segments
            
        except Exception as e:
            logger.error(f"CSV応答のパース中にエラー: {str(e)}")
            logger.debug(f"パース対象の応答: {response}")
            return segments
    
    def _time_to_seconds(self, time_str: str) -> float:
        """
        時間文字列を秒数に変換
        
        Args:
            time_str (str): 時間文字列 (MM:SS または HH:MM:SS)
            
        Returns:
            float: 秒数
        """
        try:
            time_str = time_str.strip()
            parts = time_str.split(':')
            
            if len(parts) == 2:  # MM:SS
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds
            elif len(parts) == 3:  # HH:MM:SS
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
            else:
                raise ValueError(f"無効な時間形式: {time_str}")
                
        except (ValueError, TypeError) as e:
            logger.error(f"時間文字列の変換エラー: {time_str} - {str(e)}")
            return 0.0
    
    def _split_video_with_ffmpeg(self, input_path: str, segments: List[Dict[str, str]], output_dir: str) -> List[str]:
        """
        FFmpegを使用して動画を分割
        
        Args:
            input_path (str): 入力動画ファイルのパス
            segments (List[Dict[str, str]]): セグメント情報のリスト
            output_dir (str): 出力ディレクトリ
            
        Returns:
            List[str]: 生成されたファイルのパスのリスト
        """
        split_files = []
        input_file = Path(input_path)
        output_path = Path(output_dir)
        
        # 今日の日付を取得
        today = datetime.now().strftime("%Y%m%d")
        
        for i, segment in enumerate(segments):
            try:
                event_id = segment['event_id']
                start_time = segment['start_time']
                end_time = segment['end_time']
                
                # 開始・終了時間を秒数に変換
                start_seconds = self._time_to_seconds(start_time)
                end_seconds = self._time_to_seconds(end_time)
                duration = end_seconds - start_seconds
                
                if duration <= 0:
                    logger.warning(f"セグメント {event_id} の時間が無効です: {start_time} - {end_time}")
                    continue
                
                # 出力ファイル名を生成: {event_id}_{日付}.mp4
                safe_event_id = re.sub(r'[^\w\-_.]', '_', event_id)
                output_filename = f"{safe_event_id}_{today}.mp4"
                output_file_path = output_path / output_filename
                
                # FFmpegコマンドを実行
                cmd = [
                    str(self.ffmpeg_path),
                    '-i', str(input_file),
                    '-ss', str(start_seconds),
                    '-t', str(duration),
                    '-c', 'copy',  # 再エンコードなしでコピー（高速）
                    '-avoid_negative_ts', 'make_zero',
                    str(output_file_path),
                    '-y'  # 上書き許可
                ]
                
                logger.info(f"分割中: {event_id} ({start_time} - {end_time})")
                logger.debug(f"FFmpegコマンド: {' '.join(cmd)}")
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8'
                )
                
                if result.returncode == 0:
                    split_files.append(str(output_file_path))
                    logger.info(f"分割完了: {output_filename}")
                else:
                    logger.error(f"FFmpeg分割エラー: {result.stderr}")
                    logger.warning(f"セグメント {event_id} の分割をスキップしました")
                
            except Exception as e:
                logger.error(f"セグメント {event_id} の分割中にエラー: {str(e)}")
                continue
        
        return split_files
    
    def _save_segments_to_csv(self, segments: List[Dict[str, str]], output_dir: str) -> str:
        """
        セグメント情報をCSVファイルに保存
        
        Args:
            segments (List[Dict[str, str]]): セグメント情報
            output_dir (str): 出力ディレクトリ
            
        Returns:
            str: 生成されたCSVファイルのパス
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"video_segments_{timestamp}.csv"
            csv_path = Path(output_dir) / csv_filename
            
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['event_id', 'start_time', 'end_time']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for segment in segments:
                    writer.writerow(segment)
            
            logger.info(f"セグメント情報をCSVに保存: {csv_path}")
            return str(csv_path)
            
        except Exception as e:
            logger.error(f"CSV保存中にエラー: {str(e)}")
            return ""
    
    def _analyze_video_with_custom_prompt(self, video_path: str, prompt: str) -> str:
        """
        カスタムプロンプトを使用してGemini APIで動画を解析
        
        Args:
            video_path (str): 動画ファイルのパス
            prompt (str): 分析用のプロンプト
            
        Returns:
            str: Gemini APIからの応答
        """
        try:
            # ファイルをアップロード
            uploaded_file = self.gemini_api.upload_file(video_path)
            
            # コンテンツとして、アップロードしたファイルとプロンプトを渡す
            contents = [
                uploaded_file,
                prompt
            ]
            
            # 温度や最大トークン数などのパラメータ設定
            generation_config = {
                "temperature": 0.1,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
                "response_mime_type": "text/plain",
            }
            
            logger.info(f"カスタムプロンプトで動画解析を実行: {self.gemini_api.transcription_model}")
            
            # 応答を生成
            response = self.gemini_api.client.models.generate_content(
                model=self.gemini_api.transcription_model,
                contents=contents,
                config=generation_config,
            )
            
            if hasattr(response, 'text') and response.text:
                return response.text
            else:
                raise GeminiAPIError("Gemini APIからの応答が空です")
                
        except Exception as e:
            error_msg = f"動画解析に失敗しました: {str(e)}"
            logger.error(error_msg)
            raise GeminiAPIError(error_msg)
        finally:
            # アップロードしたファイルの削除を試みる
            try:
                if 'uploaded_file' in locals():
                    # ファイルの削除がサポートされている場合
                    if hasattr(uploaded_file, 'delete'):
                        uploaded_file.delete()
                        logger.info(f"Uploaded file deleted: {uploaded_file.uri}")
            except Exception as e:
                logger.warning(f"アップロードファイルの削除に失敗しました: {str(e)}") 