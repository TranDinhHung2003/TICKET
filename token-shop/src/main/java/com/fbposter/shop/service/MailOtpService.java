package com.fbposter.shop.service;

import com.fbposter.shop.config.AppProperties;
import com.fbposter.shop.domain.OtpCode;
import com.fbposter.shop.repository.OtpCodeRepository;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.security.SecureRandom;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Optional;

@Service
public class MailOtpService {

    private final JavaMailSender mailSender;
    private final OtpCodeRepository otpRepo;
    private final AppProperties props;
    private final SecureRandom random = new SecureRandom();

    public MailOtpService(JavaMailSender mailSender, OtpCodeRepository otpRepo, AppProperties props) {
        this.mailSender = mailSender;
        this.otpRepo = otpRepo;
        this.props = props;
    }

    @Transactional
    public String sendOtp(String email, String purpose) {
        String code = String.format("%06d", random.nextInt(1_000_000));
        OtpCode otp = new OtpCode();
        otp.setEmail(email.trim().toLowerCase());
        otp.setCode(code);
        otp.setPurpose(purpose);
        otp.setExpiresAt(Instant.now().plus(props.getOtpExpireMinutes(), ChronoUnit.MINUTES));
        otpRepo.save(otp);

        try {
            SimpleMailMessage msg = new SimpleMailMessage();
            msg.setFrom(props.getMailFrom());
            msg.setTo(email);
            msg.setSubject("[" + props.getName() + "] Mã OTP xác minh");
            msg.setText("Mã OTP của bạn: " + code + "\nHiệu lực " + props.getOtpExpireMinutes()
                    + " phút.\nKhông chia sẻ mã này.");
            mailSender.send(msg);
        } catch (Exception ex) {
            // Dev mode: vẫn lưu OTP, log ra console
            System.out.println("[DEV OTP] " + email + " / " + purpose + " = " + code + " (" + ex.getMessage() + ")");
        }
        return code; // chỉ dùng khi debug; production không trả về controller
    }

    @Transactional
    public boolean verifyOtp(String email, String purpose, String code) {
        Optional<OtpCode> opt = otpRepo.findTopByEmailIgnoreCaseAndPurposeAndUsedFalseOrderByCreatedAtDesc(
                email.trim().toLowerCase(), purpose);
        if (opt.isEmpty()) return false;
        OtpCode otp = opt.get();
        if (otp.isUsed() || otp.getExpiresAt().isBefore(Instant.now())) return false;
        if (!otp.getCode().equals(code.trim())) return false;
        otp.setUsed(true);
        otpRepo.save(otp);
        return true;
    }

    public void sendTokenEmail(String to, String token, String planName, String duration, Instant expiresAt) {
        try {
            SimpleMailMessage msg = new SimpleMailMessage();
            msg.setFrom(props.getMailFrom());
            msg.setTo(to);
            msg.setSubject("[" + props.getName() + "] Token bản quyền của bạn");
            msg.setText("""
                    Cảm ơn bạn đã mua hàng!

                    Gói: %s
                    Thời hạn: %s
                    (Đồng hồ thời hạn bắt đầu khi bạn kích hoạt token trên máy)

                    MÃ TOKEN:
                    %s

                    Hướng dẫn chạy tool:
                    1. Mở Facebook Group Poster trên máy của bạn
                    2. Dán token vào ô kích hoạt License
                    3. Mỗi token chỉ dùng được 1 máy
                    4. Xem lại token tại: %s/account/orders

                    Ghi chú hệ thống (ước tính): %s
                    """.formatted(planName, duration, token, props.getBaseUrl(), expiresAt));
            mailSender.send(msg);
        } catch (Exception ex) {
            System.out.println("[DEV MAIL TOKEN] to=" + to + " token=" + token + " err=" + ex.getMessage());
        }
    }
}
