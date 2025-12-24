package com.dankook.mlpa_gradi.controller;

import com.dankook.mlpa_gradi.dto.PresignRequest;
import com.dankook.mlpa_gradi.dto.PresignResponse;
import com.dankook.mlpa_gradi.service.S3PresignService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/storage")
public class StorageController {

    private final S3PresignService s3PresignService;

    @PostMapping("/presigned-url")
    public PresignResponse createPresignedUrl(@RequestBody PresignRequest request) {
        return s3PresignService.createPutUrl(request);
    }
}
