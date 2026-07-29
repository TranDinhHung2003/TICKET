package com.fbposter.shop.repository;

import com.fbposter.shop.domain.ProductPlan;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface ProductPlanRepository extends JpaRepository<ProductPlan, Long> {
    List<ProductPlan> findByActiveTrueOrderBySortOrderAscIdAsc();
    List<ProductPlan> findAllByOrderBySortOrderAscIdAsc();
}
