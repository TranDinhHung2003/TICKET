package com.fbposter.shop.repository;

import com.fbposter.shop.domain.OtpCode;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;

public interface OtpCodeRepository extends JpaRepository<OtpCode, Long> {
    Optional<OtpCode> findTopByEmailIgnoreCaseAndPurposeAndUsedFalseOrderByCreatedAtDesc(
            String email, String purpose);
}
