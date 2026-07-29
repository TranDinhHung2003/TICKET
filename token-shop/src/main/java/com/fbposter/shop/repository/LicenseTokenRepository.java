package com.fbposter.shop.repository;

import com.fbposter.shop.domain.LicenseToken;
import com.fbposter.shop.domain.UserAccount;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.Optional;

public interface LicenseTokenRepository extends JpaRepository<LicenseToken, Long> {
    Optional<LicenseToken> findByToken(String token);
    List<LicenseToken> findByOwnerOrderByCreatedAtDesc(UserAccount owner);
    List<LicenseToken> findAllByOrderByCreatedAtDesc();
}
