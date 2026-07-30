package com.fbposter.shop.repository;

import com.fbposter.shop.domain.*;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.Optional;

public interface UserAccountRepository extends JpaRepository<UserAccount, Long> {
    Optional<UserAccount> findByEmailIgnoreCase(String email);
    Optional<UserAccount> findByGoogleId(String googleId);
    boolean existsByEmailIgnoreCase(String email);
}
