package com.dankook.mlpa_gradi.controller;

import com.dankook.mlpa_gradi.dto.ExamDto;
import com.dankook.mlpa_gradi.entity.Exam;
import com.dankook.mlpa_gradi.service.ExamService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/exams")
public class ExamController {

    private final ExamService examService;

    // ✅ 전체 시험 조회
    @GetMapping
    public List<ExamDto> getAll() {
        return examService.getAll();
    }

    // ✅ 단일 시험 조회
    @GetMapping("/{examId}")
    public ExamDto getOne(@PathVariable Long examId) {
        return examService.getOne(examId);
    }

    // ✅ 시험 생성
    @PostMapping
    public ExamDto create(@RequestBody Exam exam) {
        return examService.create(exam);
    }

    // ✅ 시험 수정
    @PutMapping("/{examId}")
    public ExamDto update(@PathVariable Long examId, @RequestBody Exam req) {
        return examService.update(examId, req);
    }

    // ✅ 시험 삭제
    @DeleteMapping("/{examId}")
    public void delete(@PathVariable Long examId) {
        examService.delete(examId);
    }
}
