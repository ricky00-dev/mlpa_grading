package com.dankook.mlpa_gradi.service;

import lombok.RequiredArgsConstructor;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.reactive.function.client.WebClient;

import java.io.IOException;

@Service
@RequiredArgsConstructor
public class FileForwardService {

    private final WebClient aiWebClient;

    // AI 서버 업로드 엔드포인트 (AI 쪽이 이 경로로 받는다고 가정)
    private static final String AI_UPLOAD_PATH = "/api/upload";

    public void forwardToAi(MultipartFile file, Long examId, String type) {
        try {
            MultipartBodyBuilder builder = new MultipartBodyBuilder();

            // 파일을 Resource로 변환 + 파일명 유지
            ByteArrayResource resource = new ByteArrayResource(file.getBytes()) {
                @Override
                public String getFilename() {
                    return file.getOriginalFilename();
                }
            };

            builder.part("file", resource)
                    .contentType(MediaType.APPLICATION_OCTET_STREAM);

            if (examId != null) builder.part("examId", examId.toString());
            if (type != null) builder.part("type", type);

            aiWebClient.post()
                    .uri(AI_UPLOAD_PATH)
                    .contentType(MediaType.MULTIPART_FORM_DATA)
                    .bodyValue(builder.build())
                    .retrieve()
                    .toBodilessEntity()
                    .block();

        } catch (IOException e) {
            throw new RuntimeException("Failed to forward file to AI server", e);
        }
    }
}
