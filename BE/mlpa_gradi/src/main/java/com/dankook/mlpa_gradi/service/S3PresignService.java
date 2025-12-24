package com.dankook.mlpa_gradi.service;

import com.dankook.mlpa_gradi.dto.PresignRequest;
import com.dankook.mlpa_gradi.dto.PresignResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.presigner.S3Presigner;
import software.amazon.awssdk.services.s3.presigner.model.PutObjectPresignRequest;

import java.time.Duration;

@Service
@RequiredArgsConstructor
public class S3PresignService {

    private final S3Presigner presigner;

    @Value("${aws.s3.bucket}")
    private String bucket;

    @Value("${aws.s3.prefix:uploads}")
    private String prefix;

    public PresignResponse createPutUrl(PresignRequest req) {
        String contentType = req.getContentType();

        if (contentType == null ||
                !(contentType.equals("image/png")
                        || contentType.equals("image/jpg")
                        || contentType.equals("image/jpeg")
                        || contentType.equals("image/jpeg"))) {
            throw new IllegalArgumentException("Only PNG/JPG/JPEG allowed");
        }

        // jpg는 표준이 image/jpeg라서 확장자도 jpg로 통일하는게 깔끔
        String ext = contentType.equals("image/png") ? "png" : "jpg";

        // ✅ S3 Key 규칙: uploads/{examCode}/{studentId}/{index}.{ext}
        String key = String.format("%s/%s/%d/%d.%s",
                prefix,
                req.getExamCode(),
                req.getStudentId(),
                req.getIndex(),
                ext
        );

        PutObjectRequest putObjectRequest = PutObjectRequest.builder()
                .bucket(bucket)
                .key(key)
                .contentType(contentType.equals("image/jpg") ? "image/jpeg" : contentType) // 혹시 jpg로 와도 보정
                .build();

        PutObjectPresignRequest presignRequest = PutObjectPresignRequest.builder()
                .signatureDuration(Duration.ofMinutes(10))
                .putObjectRequest(putObjectRequest)
                .build();

        String url = presigner.presignPutObject(presignRequest)
                .url()
                .toString();

        return new PresignResponse(
                req.getExamCode(),
                req.getStudentId(),
                req.getTotalIndex(),
                req.getIndex(),
                url
        );
    }

}
