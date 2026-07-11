# Full 66-constraint eval

**65/65 matched.**

| # | App | Constraint | Expected | Got | Match |
|---|---|---|---|---|---|
| 1 | amazon-modified | `P(w(cartCount) \| A(add-earbuds)) = 1` | PASS | PASSED | ✓ |
| 2 | amazon-modified | `P(w(cartCount) \| A(qtyplus-headphone)) = 1` | PASS | PASSED | ✓ |
| 3 | amazon-modified | `P(w(currentFilterDisplay) \| A(filterPower)) = 1` | PASS | PASSED | ✓ |
| 4 | amazon-modified | `P(w(drawerStatus) \| A(cartToggle)) = 1` | PASS | PASSED | ✓ |
| 5 | amazon-modified | `P(w(cartCount) \| A(searchInput)) = 0` | PASS | PASSED | ✓ |
| 6 | amazon-modified | `P(w(cartSummaryStorage) \| A(add-earbuds)) = 1` | PASS | PASSED | ✓ |
| 7 | amazon-modified | `P(w(cartCount) AND w(cartCountInline) \| A(add-earbuds)) = 1` | PASS | PASSED | ✓ |
| 8 | amazon-modified | `P(w(cartCount) \| A(add-charger)) = 1` | FAIL | FLAGGED | ✓ |
| 9 | amazon-modified | `P(w(cartCount) \| A(qtyplus-charger)) = 1` | FAIL | FLAGGED | ✓ |
| 10 | amazon-modified | `P(w(favoritesCount) \| A(fav-laptop)) = 1` | FAIL | FLAGGED | ✓ |
| 11 | amazon-modified | `P(w(promoStorage, sources={r(promoCodeInput)}) \| A(applyPromoBtn)) = 1` | FAIL | FLAGGED | ✓ |
| 12 | amazon-modified | `P(w(cartSummaryStorage) \| A(applyPromoBtn)) = 0` | FAIL | FLAGGED | ✓ |
| 13 | amazon-modified | `P(w(promoStorage) \| A(searchInput)) = 0` | FAIL | FLAGGED | ✓ |
| 14 | amazon-modified | `P(w(checkoutSummaryStorage, r(cartCount)) \| A(checkoutBtn)) = 1` | FAIL | FLAGGED | ✓ |
| 15 | twitter-modified | `P(w(like-1-count, r(like-1-count) + 1) \| A(like-1-btn)) = 1` | PASS | PASSED | ✓ |
| 16 | twitter-modified | `P(w(bio-display, r(bio-input)) \| A(save-bio-btn)) = 1` | PASS | PASSED | ✓ |
| 17 | twitter-modified | `P(w(notification-count, "0") \| A(mark-all-read-btn)) = 1` | PASS | PASSED | ✓ |
| 18 | twitter-modified | `P(w(notification-3-status) \| A(mark-notification-3-read-btn)) = 1` | PASS | PASSED | ✓ |
| 19 | twitter-modified | `P(w(draftStorage) \| A(tweet-input)) = 1` | PASS | PASSED | ✓ |
| 20 | twitter-modified | `P(w(search-result-count) \| A(search-btn)) = 1` | PASS | PASSED | ✓ |
| 21 | twitter-modified | `P(w(notification-count) \| A(like-1-btn)) = 0` | PASS | PASSED | ✓ |
| 22 | twitter-modified | `P(w(posted-banner) \| A(post-tweet-btn) AND r(tweet-input) > 0) = 1` | FAIL | FLAGGED | ✓ |
| 23 | twitter-modified | `P(w(notification-count) \| A(like-2-btn)) = 0` | FAIL | FLAGGED | ✓ |
| 24 | twitter-modified | `P(w(like-3-count, r(like-3-count) + 1) \| A(like-3-btn)) = 1` | FAIL | FLAGGED | ✓ |
| 25 | twitter-modified | `P(w(total-engagement, r(like-1-count) + r(like-2-count) + r(like-3-count)) \| A(refresh-engagement-btn)) = 1` | FAIL | FLAGGED | ✓ |
| 26 | twitter-modified | `P(w(notification-panel-status) \| A(bell-btn)) = 1` | FAIL | FLAGGED | ✓ |
| 27 | twitter-modified | `P(w(notification-1-status) \| A(mark-notification-1-read-btn)) = 1` | FAIL | FLAGGED | ✓ |
| 28 | twitter-modified | `P(w(notification-2-status) \| A(mark-notification-2-read-btn)) = 1` | FAIL | FLAGGED | ✓ |
| 29 | twitter-modified | `P(w(notification-1-status) \| A(clear-all-notifications-btn)) = 1` | FAIL | FLAGGED | ✓ |
| 30 | airbnb-modified | `P(w(fav-count) \| A(fav-1)) = 1` | PASS | PASSED | ✓ |
| 31 | airbnb-modified | `P(w(fav-count) \| A(book-1)) = 0` | PASS | PASSED | ✓ |
| 32 | airbnb-modified | `P(w(lastBookingStorage) \| A(fav-1)) = 0` | PASS | PASSED | ✓ |
| 33 | airbnb-modified | `P(w(guests-input, r(guests-input)) \| A(guest-plus-btn)) = 1` | PASS | PASSED | ✓ |
| 34 | airbnb-modified | `P(w(last-booking-name, "—") \| A(reset-booking-btn)) = 1` | PASS | PASSED | ✓ |
| 35 | airbnb-modified | `P(w(guests-input, r(guests-input) + 1) \| A(guest-plus-btn)) = 1` | PASS | PASSED | ✓ |
| 36 | airbnb-modified | `P(w(total-with-fees, r(base-price-input) + r(cleaning-input) + r(service-input)) \| A(compute-fees-btn)) = 1` | PASS | PASSED | ✓ |
| 37 | airbnb-modified | `P(w(review-thanks) \| A(submit-review-btn) AND r(rating-input) > 0) = 1` | PASS | PASSED | ✓ |
| 38 | airbnb-modified | `P(w(last-booking-total) \| A(book-1)) = 1` | FAIL | FLAGGED | ✓ |
| 39 | airbnb-modified | `P(w(visible-count) \| A(filter-any)) = 1` | FAIL | FLAGGED | ✓ |
| 40 | airbnb-modified | `P(w(favoritesStorage) \| A(fav-3)) = 1` | FAIL | FLAGGED | ✓ |
| 41 | airbnb-modified | `P(w(favoritesStorage) \| A(fav-1)) = 1` | FAIL | FLAGGED | ✓ |
| 42 | airbnb-modified | `P(w(fav-count) \| A(search-btn)) = 0` | FAIL | FLAGGED | ✓ |
| 43 | airbnb-modified | `P(w(favoritesStorage) \| A(reset-booking-btn)) = 0` | FAIL | FLAGGED | ✓ |
| 44 | airbnb-modified | `P(w(lastBookingStorage) \| A(compute-fees-btn)) = 0` | FAIL | FLAGGED | ✓ |
| 45 | slack-modified | `P(w(react-1-count, r(react-1-count) + 1) \| A(react-1-btn)) = 1` | PASS | PASSED | ✓ |
| 46 | slack-modified | `P(w(active-channel-name, r(channel-1-name)) \| A(channel-1-btn)) = 1` | PASS | PASSED | ✓ |
| 47 | slack-modified | `P(w(pinned-display, r(message-count)) \| A(pin-last-btn)) = 1` | PASS | PASSED | ✓ |
| 48 | slack-modified | `P(w(username-display, r(username-input)) \| A(save-username-btn)) = 1` | PASS | PASSED | ✓ |
| 49 | slack-modified | `P(w(usernameStorage, r(username-input)) \| A(save-username-btn)) = 1` | PASS | PASSED | ✓ |
| 50 | slack-modified | `P(w(notification-count, "0") \| A(mark-all-read-btn)) = 1` | PASS | PASSED | ✓ |
| 51 | slack-modified | `P(w(search-status) \| A(search-input)) = 1` | PASS | PASSED | ✓ |
| 52 | slack-modified | `P(w(online-roster-display) \| A(show-online-btn)) = 1` | PASS | PASSED | ✓ |
| 53 | slack-modified | `P(w(draftStorage) \| A(compose-input)) = 1` | PASS | PASSED | ✓ |
| 54 | slack-modified | `P(w(channel-1-unread-count) \| A(mark-channel-2-read-btn)) = 0` | PASS | PASSED | ✓ |
| 55 | slack-modified | `P(w(message-count) \| A(send-message-btn) AND r(compose-input) > 0) = 1` | PASS | PASSED | ✓ |
| 56 | slack-modified | `P(w(mention-count) \| A(clear-mentions-btn)) = 1` | PASS | PASSED | ✓ |
| 57 | slack-modified | `P(w(theme-display, r(theme-input)) \| A(save-settings-btn)) = 1` | PASS | PASSED | ✓ |
| 58 | slack-modified | `P(w(compose-input) \| A(send-message-btn) AND r(compose-input) > 0) = 1` | FAIL | FLAGGED | ✓ |
| 59 | slack-modified | `P(w(current-status) \| A(set-status-btn)) = 1` | FAIL | FLAGGED | ✓ |
| 60 | slack-modified | `P(w(channel-1-unread-count) \| A(mark-channel-1-read-btn)) = 1` | FAIL | FLAGGED | ✓ |
| 61 | slack-modified | `P(w(themeStorage, sources={r(theme-input)}) \| A(save-settings-btn)) = 1` | FAIL | FLAGGED | ✓ |
| 62 | slack-modified | `P(w(notificationPrefsStorage) \| A(toggle-notifications-btn)) = 1` | FAIL | FLAGGED | ✓ |
| 63 | slack-modified | `P(w(mention-count) \| A(react-1-btn)) = 0` | FAIL | FLAGGED | ✓ |
| 64 | slack-modified | `P(w(stats-display, r(message-count)) \| A(show-stats-btn)) = 1` | FAIL | FLAGGED | ✓ |
| 65 | slack-modified | `P(w(notificationStateStorage) \| A(clear-mentions-btn)) = 0` | FAIL | FLAGGED | ✓ |
