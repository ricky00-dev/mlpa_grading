package com.dankook.mlpa_gradi.service;

import com.dankook.mlpa_gradi.dto.ExamDto;
import com.dankook.mlpa_gradi.entity.Exam;
import com.dankook.mlpa_gradi.mapper.ExamMapper;
import com.dankook.mlpa_gradi.repository.ExamRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.NoSuchElementException;

@Service
@RequiredArgsConstructor
@Transactional
public class ExamService {

    private final ExamRepository examRepository;

    // ✅ 전체 시험 조회
    @Transactional(readOnly = true)
    public List<ExamDto> getAll() {
        return examRepository.findAll(Sort.by(Sort.Direction.DESC, "examDate"))
                .stream()
                .map(ExamMapper::toDto)
                .toList();
    }

    // ✅ 단일 시험 조회
    @Transactional(readOnly = true)
    public ExamDto getOne(Long examId) {
        Exam exam = examRepository.findById(examId)
                .orElseThrow(() -> new NoSuchElementException("Exam not found: " + examId));
        return ExamMapper.toDto(exam);
    }

    // ✅ 시험 생성
    public ExamDto create(Exam exam) {
        Exam saved = examRepository.save(exam);
        return ExamMapper.toDto(saved);
    }

    // ✅ 시험 수정
    public ExamDto update(Long examId, Exam req) {
        Exam exam = examRepository.findById(examId)
                .orElseThrow(() -> new NoSuchElementException("Exam not found: " + examId));

        exam.setExamName(req.getExamName());
        exam.setExamDate(req.getExamDate());

        Exam saved = examRepository.save(exam);
        return ExamMapper.toDto(saved);
    }

    // ✅ 시험 삭제
    public void delete(Long examId) {
        if (!examRepository.existsById(examId)) {
            throw new NoSuchElementException("Exam not found: " + examId);
        }
        examRepository.deleteById(examId);
    }
}
