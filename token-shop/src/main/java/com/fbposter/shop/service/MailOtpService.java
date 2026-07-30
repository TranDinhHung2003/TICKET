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

        String subject;
        String body;
        if ("REGISTER".equalsIgnoreCase(purpose)) {
            subject = "[" + props.getName() + "] Mã OTP đăng ký tài khoản";
            body = "Xin chào,\n\n"
                    + "Bạn đang đăng ký tài khoản trên " + props.getName() + ".\n"
                    + "Mã OTP xác minh Gmail của bạn là:\n\n"
                    + "    " + code + "\n\n"
                    + "Mã có hiệu lực " + props.getOtpExpireMinutes() + " phút.\n"
                    + "Không chia sẻ mã này cho người khác.\n\n"
                    + "Nếu bạn không yêu cầu đăng ký, hãy bỏ qua email này.\n\n"
                    + "— " + props.getName() + "\n"
                    + "Bản quyền thuộc về TranDinhHung\n"
                    + "Zalo/SĐT hỗ trợ: 0981227703\n";
        } else {
            subject = "[" + props.getName() + "] Mã OTP xác minh";
            body = "Mã OTP của bạn: " + code + "\nHiệu lực " + props.getOtpExpireMinutes()
                    + " phút.\nKhông chia sẻ mã này.";
        }

        try {
            SimpleMailMessage msg = new SimpleMailMessage();
            msg.setFrom(props.getMailFrom());
            msg.setTo(email);
            msg.setSubject(subject);
            msg.setText(body);
            mailSender.send(msg);
        } catch (Exception ex) {
            // Dev mode: vẫn lưu OTP, log ra console khi chưa cấu hình SMTP
            System.out.println("[DEV OTP] " + email + " / " + purpose + " = " + code + " (" + ex.getMessage() + ")");
        }
        return code;
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

                    Token của bạn sẽ được lưu trong đơn hàng trên website.

                    Hướng dẫn chạy tool:
                    1. Mở Facebook Group Poster trên máy của bạn
                    2. Dán token vào ô kích hoạt License
                    3. Mỗi token chỉ dùng được 1 máy
                    4. Xem lại token tại: %s/account/orders

                    Hỗ trợ Zalo/SĐT: 0981227703
                    © Bản quyền thuộc về TranDinhHung
                    """.formatted(planName, duration, token, props.getBaseUrl()));
            mailSender.send(msg);
        } catch (Exception ex) {
            System.out.println("[DEV MAIL TOKEN] to=" + to + " token=" + token + " err=" + ex.getMessage());
        }
    }
}
