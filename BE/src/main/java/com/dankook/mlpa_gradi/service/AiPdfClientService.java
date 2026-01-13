package com.dankook.mlpa_gradi.service;

import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

@Service
@RequiredArgsConstructor
public class AiPdfClientService {

    private final WebClient aiWebClient;

    /**
     * FastAPI:
     * GET /pdf/course-stats?subject=MLPA
     */
    public byte[] fetchCourseStatsPdf(String subject) {
        try {
            return aiWebClient.get()
                    .uri(uriBuilder -> uriBuilder
                            .path("/pdf/course-stats")
                            .queryParam("subject", subject)
                            .build())
                    .accept(MediaType.APPLICATION_PDF)
                    .retrieve()
                    .bodyToMono(byte[].class)
                    .block();
        } catch (WebClientResponseException e) {
            throw new IllegalStateException(
                    "AI PDF server error: status=" + e.getStatusCode()
                            + ", body=" + e.getResponseBodyAsString(), e
            );
        } catch (Exception e) {
            throw new IllegalStateException("Failed to call AI PDF server", e);
        }
    }
}
