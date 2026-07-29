package com.fbposter.shop.repository;

import com.fbposter.shop.domain.OrderStatus;
import com.fbposter.shop.domain.ShopOrder;
import com.fbposter.shop.domain.UserAccount;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.Optional;

public interface ShopOrderRepository extends JpaRepository<ShopOrder, Long> {
    Optional<ShopOrder> findByPaymentCode(String paymentCode);
    List<ShopOrder> findByUserOrderByCreatedAtDesc(UserAccount user);
    List<ShopOrder> findByStatusOrderByCreatedAtDesc(OrderStatus status);
    List<ShopOrder> findAllByOrderByCreatedAtDesc();
}
