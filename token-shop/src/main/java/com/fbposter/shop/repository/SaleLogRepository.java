package com.fbposter.shop.repository;

import com.fbposter.shop.domain.SaleLog;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface SaleLogRepository extends JpaRepository<SaleLog, Long> {
    List<SaleLog> findAllByOrderByCreatedAtDesc();
}
