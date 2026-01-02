"""
sqs_schemas.py - SQS 메시지 스키마 정의

BE ↔ AI 서버 간 SQS 메시지 포맷을 정의합니다.
모든 JSON 필드는 camelCase를 사용합니다.

Event Types:
- ATTENDANCE_UPLOAD: 출석부 업로드 알림
- STUDENT_ID_RECOGNITION: 이미지 학번 추출 요청/결과
"""

from dataclasses import dataclass, field
from typing import Optional, Literal
import json


# =============================================================================
# Constants
# =============================================================================
EVENT_ATTENDANCE_UPLOAD = "ATTENDANCE_UPLOAD"
EVENT_STUDENT_ID_RECOGNITION = "STUDENT_ID_RECOGNITION"
UNKNOWN_ID = "unknown_id"


def to_camel_case(snake_str: str) -> str:
    """snake_case를 camelCase로 변환"""
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def dict_to_camel_case(d: dict) -> dict:
    """딕셔너리의 모든 키를 camelCase로 변환"""
    return {to_camel_case(k): v for k, v in d.items() if v is not None}


# =============================================================================
# BE → AI: 입력 메시지 (SQS에서 수신)
# =============================================================================
@dataclass
class SQSInputMessage:
    """
    백엔드에서 AI 서버로 전송되는 SQS 메시지
    
    Event Types:
    - ATTENDANCE_UPLOAD: 출석부 다운로드 요청
    - STUDENT_ID_RECOGNITION: 이미지 학번 추출 요청
    """
    event_type: str
    exam_code: str
    file_name: str
    index: int
    total: int
    image_url: Optional[str] = None      # STUDENT_ID_RECOGNITION 시
    download_url: Optional[str] = None   # ATTENDANCE_UPLOAD 시
    receipt_handle: Optional[str] = None  # SQS 메시지 삭제용 (내부 사용)
    
    @classmethod
    def from_sqs_message(cls, body: dict, receipt_handle: str = None) -> "SQSInputMessage":
        """
        SQS 메시지 Body(camelCase JSON)에서 객체 생성
        """
        return cls(
            event_type=body.get("eventType", ""),
            exam_code=body.get("examCode", ""),
            file_name=body.get("fileName", ""),
            index=body.get("index", 0),
            total=body.get("total", 0),
            image_url=body.get("imageUrl"),
            download_url=body.get("downloadUrl"),
            receipt_handle=receipt_handle
        )


# =============================================================================
# AI → BE: 출력 메시지 (SQS로 전송)
# =============================================================================
@dataclass
class SQSOutputMessage:
    """
    AI 서버에서 백엔드로 전송하는 SQS 결과 메시지
    """
    event_type: str
    exam_code: str
    student_id: str  # 실패 시 "unknown_id"
    file_name: str
    index: int
    total: Optional[int] = None
    
    def to_dict(self) -> dict:
        """camelCase 딕셔너리로 변환"""
        d = {
            "eventType": self.event_type,
            "examCode": self.exam_code,
            "studentId": self.student_id,
            "fileName": self.file_name,
            "index": self.index,
        }
        if self.total is not None:
            d["total"] = self.total
        return d
    
    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def create(
        cls,
        exam_code: str,
        student_id: Optional[str],
        file_name: str,
        index: int,
        total: Optional[int] = None,
        event_type: str = EVENT_STUDENT_ID_RECOGNITION
    ) -> "SQSOutputMessage":
        """
        팩토리 메서드: 결과 메시지 생성
        
        Args:
            exam_code: 시험 코드
            student_id: 추출된 학번 (None이면 unknown_id)
            file_name: 파일명
            index: 순차 인덱스
            total: 전체 이미지 수 (선택)
            event_type: 이벤트 타입
        """
        effective_student_id = student_id if student_id else UNKNOWN_ID
        
        return cls(
            event_type=event_type,
            exam_code=exam_code,
            student_id=effective_student_id,
            file_name=file_name,
            index=index,
            total=total
        )


# =============================================================================
# Fallback API 스키마
# =============================================================================
@dataclass
class FallbackImageItem:
    """Fallback 요청의 개별 이미지 항목"""
    file_name: str
    student_id: str
    
    @classmethod
    def from_dict(cls, d: dict) -> "FallbackImageItem":
        return cls(
            file_name=d.get("fileName", ""),
            student_id=d.get("studentId", "")
        )


@dataclass
class FallbackRequest:
    """
    사용자 Fallback 요청 스키마
    
    Request Body (camelCase):
    {
        "examCode": "ABCDEF",
        "images": [
            {"fileName": "image1.jpg", "studentId": "32204077"},
            ...
        ]
    }
    """
    exam_code: str
    images: list[FallbackImageItem] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, d: dict) -> "FallbackRequest":
        exam_code = d.get("examCode", "")
        images = [FallbackImageItem.from_dict(img) for img in d.get("images", [])]
        return cls(exam_code=exam_code, images=images)


# =============================================================================
# 테스트 코드
# =============================================================================
if __name__ == "__main__":
    print("=== SQS 입력 메시지 (BE → AI) ===")
    input_body = {
        "eventType": "STUDENT_ID_RECOGNITION",
        "examCode": "AI_2024_MID",
        "imageUrl": "s3://mlpa-gradi/uploads/exam123/page_001.jpg",
        "fileName": "page_001.jpg",
        "index": 0,
        "total": 40
    }
    input_msg = SQSInputMessage.from_sqs_message(input_body, receipt_handle="test-handle")
    print(f"event_type: {input_msg.event_type}")
    print(f"exam_code: {input_msg.exam_code}")
    print(f"image_url: {input_msg.image_url}")
    print()
    
    print("=== SQS 출력 메시지 (AI → BE) ===")
    output_msg = SQSOutputMessage.create(
        exam_code="AI_2024_MID",
        student_id="20211234",
        file_name="page_001.jpg",
        index=0,
        total=40
    )
    print(output_msg.to_json())
    print()
    
    print("=== Fallback 요청 ===")
    fallback_body = {
        "examCode": "ABCDEF",
        "images": [
            {"fileName": "image1.jpg", "studentId": "32204077"},
            {"fileName": "image2.jpg", "studentId": "32204078"}
        ]
    }
    fallback_req = FallbackRequest.from_dict(fallback_body)
    print(f"exam_code: {fallback_req.exam_code}")
    print(f"images: {[(img.file_name, img.student_id) for img in fallback_req.images]}")
