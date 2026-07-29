package com.fbposter.shop.service;

import com.fbposter.shop.domain.LicenseToken;
import com.fbposter.shop.domain.ProductPlan;
import com.fbposter.shop.domain.ShopOrder;
import com.fbposter.shop.domain.UserAccount;
import com.fbposter.shop.repository.LicenseTokenRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.security.SecureRandom;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Locale;

@Service
public class LicenseService {

    private static final String ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
    private final LicenseTokenRepository repo;
    private final SecureRandom random = new SecureRandom();

    public LicenseService(LicenseTokenRepository repo) {
        this.repo = repo;
    }

    public String generateTokenString() {
        StringBuilder sb = new StringBuilder("FBP");
        for (int g = 0; g < 4; g++) {
            sb.append('-');
            for (int i = 0; i < 4; i++) {
                sb.append(ALPHABET.charAt(random.nextInt(ALPHABET.length())));
            }
        }
        return sb.toString();
    }

    public Instant calcExpiry(ProductPlan plan) {
        Instant now = Instant.now();
        long minutes = plan.getMinutes()
                + plan.getHours() * 60L
                + plan.getDays() * 24L * 60
                + plan.getMonths() * 30L * 24 * 60
                + plan.getYears() * 365L * 24 * 60;
        if (minutes <= 0) minutes = 30L * 24 * 60;
        return now.plus(minutes, ChronoUnit.MINUTES);
    }

    @Transactional
    public LicenseToken issueForOrder(ShopOrder order) {
        ProductPlan plan = order.getPlan();
        LicenseToken t = new LicenseToken();
        t.setToken(generateTokenString());
        t.setOwner(order.getUser());
        t.setOrder(order);
        t.setDurationLabel(plan.durationLabel());
        t.setExpiresAt(calcExpiry(plan));
        t.setNote("Order " + order.getPaymentCode());
        return repo.save(t);
    }

    @Transactional
    public LicenseToken adminCreate(UserAccount owner, ProductPlan plan, String note) {
        LicenseToken t = new LicenseToken();
        t.setToken(generateTokenString());
        t.setOwner(owner);
        t.setDurationLabel(plan != null ? plan.durationLabel() : "tuỳ chỉnh");
        if (plan != null) {
            t.setExpiresAt(calcExpiry(plan));
        } else {
            t.setExpiresAt(Instant.now().plus(30, ChronoUnit.DAYS));
        }
        t.setNote(note);
        return repo.save(t);
    }

    @Transactional
    public java.util.Map<String, Object> activate(String token, String machineId, String machineName, String ip) {
        token = token.trim().toUpperCase(Locale.ROOT);
        machineId = machineId.trim().toLowerCase(Locale.ROOT);
        LicenseToken lic = repo.findByToken(token).orElse(null);
        if (lic == null) return err("Token không tồn tại", "not_found");
        if (lic.isRevoked()) return err("Token đã bị thu hồi", "revoked");
        if (Instant.now().isAfter(lic.getExpiresAt())) return err("Token đã hết hạn", "expired");

        String blocked = lic.getBlockedMachineId() == null ? "" : lic.getBlockedMachineId().toLowerCase(Locale.ROOT);
        if (!blocked.isBlank() && blocked.equals(machineId)) {
            return err("Máy này đã bị gỡ khỏi token (admin reset).", "machine_blocked");
        }
        if (lic.getMachineId() != null && !lic.getMachineId().equals(machineId)) {
            return err("Token đã kích hoạt trên máy khác.", "bound_other");
        }

        Instant now = Instant.now();
        if (lic.getMachineId() == null) {
            lic.setActivatedAt(now);
            lic.setFirstIp(ip);
        }
        lic.setMachineId(machineId);
        lic.setMachineName(machineName);
        lic.setLastIp(ip);
        lic.setLastSeenAt(now);
        lic.setActivateCount(lic.getActivateCount() + 1);
        repo.save(lic);

        return java.util.Map.of(
                "ok", true,
                "message", "Kích hoạt thành công",
                "token", lic.getToken(),
                "expires_at", lic.getExpiresAt().toString(),
                "duration_label", lic.getDurationLabel(),
                "machine_id", machineId,
                "ip", ip == null ? "" : ip
        );
    }

    @Transactional
    public java.util.Map<String, Object> verify(String token, String machineId, String ip) {
        token = token.trim().toUpperCase(Locale.ROOT);
        machineId = machineId.trim().toLowerCase(Locale.ROOT);
        LicenseToken lic = repo.findByToken(token).orElse(null);
        if (lic == null) return err("Token không tồn tại", "not_found");
        if (lic.isRevoked()) return err("Token đã bị thu hồi", "revoked");
        if (Instant.now().isAfter(lic.getExpiresAt())) return err("Token đã hết hạn", "expired");

        String blocked = lic.getBlockedMachineId() == null ? "" : lic.getBlockedMachineId().toLowerCase(Locale.ROOT);
        if (!blocked.isBlank() && blocked.equals(machineId)) {
            return err("Máy này đã bị gỡ khỏi token", "machine_blocked");
        }
        if (lic.getMachineId() == null) {
            return java.util.Map.of("ok", false, "error", "Token chưa gắn máy", "code", "need_activate", "need_activate", true);
        }
        if (!lic.getMachineId().equals(machineId)) {
            return err("Token không khớp máy này", "bound_other");
        }
        lic.setLastIp(ip);
        lic.setLastSeenAt(Instant.now());
        repo.save(lic);
        long secondsLeft = Math.max(0, lic.getExpiresAt().getEpochSecond() - Instant.now().getEpochSecond());
        return java.util.Map.of(
                "ok", true,
                "expires_at", lic.getExpiresAt().toString(),
                "duration_label", lic.getDurationLabel(),
                "days_left", secondsLeft / 86400,
                "seconds_left", secondsLeft,
                "ip", ip == null ? "" : ip
        );
    }

    @Transactional
    public void revoke(String token) {
        repo.findByToken(token.trim().toUpperCase(Locale.ROOT)).ifPresent(lic -> {
            if (lic.getMachineId() != null) {
                lic.setBlockedMachineId(lic.getMachineId());
            }
            lic.setRevoked(true);
            repo.save(lic);
        });
    }

    @Transactional
    public void resetMachine(String token) {
        repo.findByToken(token.trim().toUpperCase(Locale.ROOT)).ifPresent(lic -> {
            if (lic.getMachineId() != null) {
                lic.setBlockedMachineId(lic.getMachineId());
            }
            lic.setMachineId(null);
            lic.setMachineName(null);
            lic.setActivatedAt(null);
            repo.save(lic);
        });
    }

    private java.util.Map<String, Object> err(String msg, String code) {
        return java.util.Map.of("ok", false, "error", msg, "code", code);
    }
}
