"""
sqs_worker.py - SQS Consumer Worker

백그라운드에서 SQS 메시지를 수신하고 처리합니다.

Event Types:
- ATTENDANCE_UPLOAD: presigned URL에서 출석부 다운로드 → 파싱
- STUDENT_ID_RECOGNITION: S3에서 이미지 다운로드 → 학번 추출 → 결과 전송
"""

import os
import io
import json
import time
import logging
import threading
import tempfile
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass

import boto3
import requests
import numpy as np
from PIL import Image
from botocore.exceptions import ClientError

from sqs_schemas import (
    SQSInputMessage, 
    SQSOutputMessage,
    EVENT_ATTENDANCE_UPLOAD,
    EVENT_STUDENT_ID_RECOGNITION,
    UNKNOWN_ID
)

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SQSWorker:
    """
    SQS Consumer Worker
    
    백그라운드에서 SQS로부터 메시지를 수신하고 처리합니다.
    - ATTENDANCE_UPLOAD: 출석부 다운로드 및 파싱
    - STUDENT_ID_RECOGNITION: 이미지 학번 추출
    """
    
    def __init__(
        self,
        queue_url: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region_name: str = "ap-northeast-2",
        s3_bucket: str = "mlpa-gradi"
    ):
        self.queue_url = queue_url
        self.s3_bucket = s3_bucket
        
        # SQS 클라이언트
        self.sqs = boto3.client(
            'sqs',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )
        
        # S3 클라이언트 (이미지 다운로드/업로드용)
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )
        
        # 워커 상태
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        
        # 콜백 함수
        self._student_id_callback: Optional[Callable] = None
        self._attendance_callback: Optional[Callable] = None
        
        # ExamCode별 학번 리스트 저장소
        self._student_id_lists: Dict[str, List[str]] = {}
        
        logger.info(f"SQS Worker 초기화 완료: {queue_url}")
    
    def set_student_id_callback(self, callback: Callable[[np.ndarray, List[str]], dict]):
        """
        학번 추출 콜백 함수 설정
        
        Args:
            callback: (image, student_id_list) -> {"student_id": str | None, "meta": dict}
        """
        self._student_id_callback = callback
    
    def set_attendance_callback(self, callback: Callable[[str], List[str]]):
        """
        출석부 파싱 콜백 함수 설정
        
        Args:
            callback: (file_path) -> [student_id, ...]
        """
        self._attendance_callback = callback
    
    def get_student_list(self, exam_code: str) -> List[str]:
        """특정 시험의 학번 리스트 반환"""
        return self._student_id_lists.get(exam_code, [])
    
    # =========================================================================
    # 이미지 다운로드
    # =========================================================================
    def download_image(self, image_path: str) -> Optional[np.ndarray]:
        """
        이미지 경로에서 이미지 다운로드
        
        지원 형식:
        - s3://bucket/key
        - S3 키 (bucket은 기본값 사용)
        - http/https URL
        """
        try:
            if image_path.startswith("s3://"):
                # s3://bucket/key 형식
                parts = image_path[5:].split("/", 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ""
                response = self.s3.get_object(Bucket=bucket, Key=key)
            elif image_path.startswith("http://") or image_path.startswith("https://"):
                # HTTP URL (presigned URL 등)
                resp = requests.get(image_path, timeout=60)
                resp.raise_for_status()
                pil_image = Image.open(io.BytesIO(resp.content)).convert("RGB")
                return np.array(pil_image)
            else:
                # S3 키로 간주
                response = self.s3.get_object(Bucket=self.s3_bucket, Key=image_path)
            
            image_data = response['Body'].read()
            pil_image = Image.open(io.BytesIO(image_data)).convert("RGB")
            return np.array(pil_image)
            
        except Exception as e:
            logger.error(f"이미지 다운로드 실패 ({image_path}): {e}")
            return None
    
    def download_file_from_url(self, url: str, suffix: str = ".xlsx") -> Optional[str]:
        """
        URL에서 파일 다운로드하여 임시 파일로 저장
        
        Returns:
            임시 파일 경로 (실패 시 None)
        """
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(resp.content)
                return tmp.name
        except Exception as e:
            logger.error(f"파일 다운로드 실패 ({url}): {e}")
            return None
    
    # =========================================================================
    # S3 업로드
    # =========================================================================
    def upload_image_to_s3(
        self, 
        image: np.ndarray, 
        s3_key: str,
        quality: int = 95
    ) -> bool:
        """이미지를 S3에 업로드"""
        try:
            buffer = io.BytesIO()
            Image.fromarray(image).save(buffer, format='JPEG', quality=quality)
            buffer.seek(0)
            
            self.s3.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=buffer.getvalue(),
                ContentType='image/jpeg'
            )
            logger.info(f"S3 업로드 성공: {s3_key}")
            return True
        except Exception as e:
            logger.error(f"S3 업로드 실패: {e}")
            return False
    
    # =========================================================================
    # SQS 메시지 처리
    # =========================================================================
    def receive_message(self, wait_time_seconds: int = 20) -> Optional[SQSInputMessage]:
        """SQS에서 메시지 하나를 수신"""
        try:
            response = self.sqs.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=wait_time_seconds,
                AttributeNames=['All'],
                MessageAttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            if not messages:
                return None
            
            msg = messages[0]
            body = json.loads(msg['Body'])
            
            return SQSInputMessage.from_sqs_message(body, msg['ReceiptHandle'])
            
        except Exception as e:
            logger.error(f"SQS 메시지 수신 실패: {e}")
            return None
    
    def send_result_message(self, message: SQSOutputMessage, group_id: str = "default") -> Optional[str]:
        """결과 메시지를 SQS로 전송"""
        import uuid
        
        try:
            response = self.sqs.send_message(
                QueueUrl=self.queue_url,
                MessageBody=message.to_json(),
                MessageGroupId=group_id,
                MessageDeduplicationId=str(uuid.uuid4())
            )
            msg_id = response.get('MessageId')
            logger.info(f"SQS 결과 전송: {msg_id}")
            return msg_id
        except ClientError as e:
            logger.error(f"SQS 메시지 전송 실패: {e}")
            return None
    
    def delete_message(self, receipt_handle: str) -> bool:
        """처리 완료된 메시지 삭제"""
        try:
            self.sqs.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            return True
        except ClientError as e:
            logger.error(f"SQS 메시지 삭제 실패: {e}")
            return False
    
    # =========================================================================
    # 이벤트 핸들러
    # =========================================================================
    def handle_attendance_upload(self, msg: SQSInputMessage) -> bool:
        """출석부 업로드 이벤트 처리"""
        logger.info(f"[ATTENDANCE_UPLOAD] exam={msg.exam_code}, file={msg.file_name}")
        
        if not msg.download_url:
            logger.error("downloadUrl이 없습니다.")
            return False
        
        # 1. 파일 다운로드
        tmp_path = self.download_file_from_url(msg.download_url, suffix=".xlsx")
        if not tmp_path:
            return False
        
        try:
            # 2. 출석부 파싱
            if self._attendance_callback:
                student_ids = self._attendance_callback(tmp_path)
            else:
                # 기본 파싱
                from parsing_xlsx import parsing_xlsx
                student_ids = parsing_xlsx(tmp_path)
            
            # 3. 메모리에 저장
            self._student_id_lists[msg.exam_code] = student_ids
            logger.info(f"[ATTENDANCE_UPLOAD] {msg.exam_code}: {len(student_ids)}명 로드 완료")
            
            return True
            
        finally:
            # 임시 파일 삭제
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def handle_student_id_recognition(self, msg: SQSInputMessage) -> bool:
        """이미지 학번 추출 이벤트 처리"""
        logger.info(f"[STUDENT_ID_RECOGNITION] exam={msg.exam_code}, file={msg.file_name}, index={msg.index}/{msg.total}")
        
        if not msg.image_url:
            logger.error("imageUrl이 없습니다.")
            return False
        
        # 1. 이미지 다운로드
        image = self.download_image(msg.image_url)
        if image is None:
            # 실패해도 결과는 전송
            result_msg = SQSOutputMessage.create(
                exam_code=msg.exam_code,
                student_id=None,
                file_name=msg.file_name,
                index=msg.index,
                total=msg.total
            )
            self.send_result_message(result_msg, group_id=msg.exam_code)
            return False
        
        # 2. 학번 추출
        student_id = None
        if self._student_id_callback:
            student_list = self.get_student_list(msg.exam_code)
            result = self._student_id_callback(image, student_list)
            student_id = result.get("student_id")
        
        # 3. 결과 메시지 전송
        result_msg = SQSOutputMessage.create(
            exam_code=msg.exam_code,
            student_id=student_id,
            file_name=msg.file_name,
            index=msg.index,
            total=msg.total
        )
        self.send_result_message(result_msg, group_id=msg.exam_code)
        
        # 4. S3 업로드 (성공 시 original, 실패 시 header/unknown_id)
        if student_id:
            s3_key = f"original/{msg.exam_code}/{student_id}/{msg.file_name}"
        else:
            s3_key = f"header/{msg.exam_code}/{UNKNOWN_ID}/{msg.file_name}"
        
        self.upload_image_to_s3(image, s3_key)
        
        return True
    
    def process_message(self, msg: SQSInputMessage) -> bool:
        """메시지 타입에 따라 적절한 핸들러 호출"""
        if msg.event_type == EVENT_ATTENDANCE_UPLOAD:
            return self.handle_attendance_upload(msg)
        elif msg.event_type == EVENT_STUDENT_ID_RECOGNITION:
            return self.handle_student_id_recognition(msg)
        else:
            logger.warning(f"알 수 없는 이벤트 타입: {msg.event_type}")
            return False
    
    # =========================================================================
    # 워커 루프
    # =========================================================================
    def _worker_loop(self):
        """워커 메인 루프"""
        logger.info("SQS Worker 시작 - 메시지 폴링 대기 중...")
        
        while self._running:
            try:
                # 메시지 수신 (Long Polling)
                msg = self.receive_message(wait_time_seconds=20)
                
                if msg is None:
                    continue
                
                # 메시지 처리
                success = self.process_message(msg)
                
                # 처리 완료 시 메시지 삭제
                if success and msg.receipt_handle:
                    self.delete_message(msg.receipt_handle)
                    
            except Exception as e:
                logger.error(f"Worker 에러: {e}")
                time.sleep(5)
        
        logger.info("SQS Worker 종료")
    
    def start(self):
        """워커 백그라운드 실행 시작"""
        if self._running:
            logger.warning("Worker가 이미 실행 중입니다.")
            return
        
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="SQS-Worker-Thread"
        )
        self._worker_thread.start()
        logger.info("SQS Worker가 백그라운드에서 시작되었습니다.")
    
    def stop(self):
        """워커 종료"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=25)
        logger.info("SQS Worker가 종료되었습니다.")
    
    @property
    def is_running(self) -> bool:
        return self._running


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================
_worker_instance: Optional[SQSWorker] = None


def get_sqs_worker() -> Optional[SQSWorker]:
    """SQS Worker 싱글톤 인스턴스 반환"""
    global _worker_instance
    return _worker_instance


def init_sqs_worker(
    queue_url: str,
    aws_access_key_id: str,
    aws_secret_access_key: str,
    region_name: str = "ap-northeast-2",
    s3_bucket: str = "mlpa-gradi"
) -> SQSWorker:
    """SQS Worker 초기화 및 싱글톤 설정"""
    global _worker_instance
    _worker_instance = SQSWorker(
        queue_url=queue_url,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name,
        s3_bucket=s3_bucket
    )
    return _worker_instance
