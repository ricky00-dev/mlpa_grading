package com.dankook.mlpa_gradi.repository;

import com.dankook.mlpa_gradi.entity.StudentAnswer;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface StudentAnswerRepository extends JpaRepository<StudentAnswer, Long> {

    // 시험 코드 기준 전체 답안 조회
    List<StudentAnswer> findByExamCode(String examCode);

    // 시험 코드 + 문제 번호
    List<StudentAnswer> findByExamCodeAndQuestionNumber(
            String examCode,
            int questionNumber
    );
}
