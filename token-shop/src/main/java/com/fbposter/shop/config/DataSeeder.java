package com.fbposter.shop.config;

import com.fbposter.shop.domain.ProductPlan;
import com.fbposter.shop.domain.Role;
import com.fbposter.shop.domain.UserAccount;
import com.fbposter.shop.repository.ProductPlanRepository;
import com.fbposter.shop.repository.UserAccountRepository;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

@Component
public class DataSeeder implements ApplicationRunner {

  private final UserAccountRepository userRepo;
  private final ProductPlanRepository planRepo;
  private final AppProperties props;
  private final PasswordEncoder passwordEncoder;

  public DataSeeder(
      UserAccountRepository userRepo,
      ProductPlanRepository planRepo,
      AppProperties props,
      PasswordEncoder passwordEncoder) {
    this.userRepo = userRepo;
    this.planRepo = planRepo;
    this.props = props;
    this.passwordEncoder = passwordEncoder;
  }

  @Override
  public void run(ApplicationArguments args) {
    seedAdmin();
    seedPlans();
  }

  private void seedAdmin() {
    String email = props.getAdminEmail().trim().toLowerCase();
    userRepo
        .findByEmailIgnoreCase(email)
        .ifPresentOrElse(
            u -> {
              if (u.getRole() != Role.ADMIN) {
                u.setRole(Role.ADMIN);
                u.setEmailVerified(true);
                u.setEnabled(true);
                userRepo.save(u);
              }
            },
            () -> {
              UserAccount admin = new UserAccount();
              admin.setEmail(email);
              admin.setFullName("Administrator");
              admin.setPasswordHash(passwordEncoder.encode(props.getAdminPassword()));
              admin.setRole(Role.ADMIN);
              admin.setEmailVerified(true);
              admin.setEnabled(true);
              userRepo.save(admin);
            });
  }

  private void seedPlans() {
    if (planRepo.count() > 0) {
      return;
    }
    planRepo.save(plan("Dùng thử 1 giờ", "Trải nghiệm nhanh", 0, 1, 0, 0, 0, 1000, 1));
    planRepo.save(plan("1 ngày", "Phù hợp chạy chiến dịch ngắn", 0, 0, 1, 0, 0, 29000, 2));
    planRepo.save(plan("7 ngày", "Tuần làm việc", 0, 0, 7, 0, 0, 99000, 3));
    planRepo.save(plan("30 ngày", "Gói tháng phổ biến", 0, 0, 0, 1, 0, 249000, 4));
    planRepo.save(plan("1 năm", "Tiết kiệm dài hạn", 0, 0, 0, 0, 1, 1990000, 5));
  }

  private ProductPlan plan(
      String name,
      String desc,
      int minutes,
      int hours,
      int days,
      int months,
      int years,
      long price,
      int sort) {
    ProductPlan p = new ProductPlan();
    p.setName(name);
    p.setDescription(desc);
    p.setMinutes(minutes);
    p.setHours(hours);
    p.setDays(days);
    p.setMonths(months);
    p.setYears(years);
    p.setPriceVnd(price);
    p.setSortOrder(sort);
    p.setActive(true);
    return p;
  }
}
