package com.dankook.mlpa_gradi.controller;

import com.dankook.mlpa_gradi.service.FileForwardService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/files")
public class FileForwardController {

    private final FileForwardService fileForwardService;

    @PostMapping(value = "/forward", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<String> forward(
            @RequestPart("file") MultipartFile file,
            @RequestParam(value = "examId", required = false) Long examId,
            @RequestParam(value = "type", required = false) String type
    ) {
        fileForwardService.forwardToAi(file, examId, type);
        return ResponseEntity.ok("forwarded");
    }
}
