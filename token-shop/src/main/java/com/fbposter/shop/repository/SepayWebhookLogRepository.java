package com.fbposter.shop.repository;

import com.fbposter.shop.domain.SepayWebhookLog;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;

public interface SepayWebhookLogRepository extends JpaRepository<SepayWebhookLog, Long> {
    Optional<SepayWebhookLog> findByTransactionId(Long transactionId);
    boolean existsByTransactionId(Long transactionId);
}
