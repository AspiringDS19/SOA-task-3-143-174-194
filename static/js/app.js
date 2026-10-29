const { createApp, ref, computed, onMounted } = Vue;

createApp({
  setup() {
    // Current Active Tab
    const activeTab = ref('ecommerce'); // 'ecommerce' | 'banking' | 'soa'
    const toasts = ref([]);

    // Helper: Toast Notifications
    const showToast = (message, type = 'info') => {
      const id = Date.now() + Math.random();
      toasts.value.push({ id, message, type });
      setTimeout(() => {
        toasts.value = toasts.value.filter(t => t.id !== id);
      }, 4500);
    };

    // =========================================================================
    // 1. E-COMMERCE CLIENT (NovaShop) STATE & ACTIONS
    // =========================================================================
    const products = ref([]);
    const cart = ref([]);
    const couponCode = ref('WELCOME20');
    const appliedCoupon = ref(null);
    const isCheckingOut = ref(false);
    const confirmedOrderModal = ref(null);
    const ordersHistory = ref([]);
    const customerForm = ref({
      name: 'Alex Morgan',
      email: 'alex.morgan@enterprise.org',
      address: '742 Evergreen Terrace, Suite 400, Silicon Valley, CA 94025',
      paymentMethod: 'credit_card'
    });

    const loadProducts = async () => {
      try {
        const res = await fetch('/api/ecommerce/products');
        const data = await res.json();
        if (data.success) {
          products.value = data.products;
          // Add default items to cart for instant interactive feel
          if (cart.value.length === 0 && products.value.length > 0) {
            cart.value = [
              { ...products.value[0], quantity: 1 },
              { ...products.value[3], quantity: 1 }
            ];
          }
        }
      } catch (err) {
        showToast('Failed to load product catalog: ' + err.message, 'error');
      }
    };

    const loadOrdersHistory = async () => {
      try {
        const res = await fetch('/api/ecommerce/orders');
        const data = await res.json();
        if (data.success) ordersHistory.value = data.orders;
      } catch (err) {
        console.error(err);
      }
    };

    const addToCart = (product) => {
      const existing = cart.value.find(item => item.id === product.id);
      if (existing) {
        if (existing.quantity < product.stock) {
          existing.quantity++;
          showToast(`Increased ${product.name} quantity to ${existing.quantity}`, 'info');
        } else {
          showToast(`Maximum stock limit reached for ${product.name}`, 'error');
        }
      } else {
        cart.value.push({ ...product, quantity: 1 });
        showToast(`Added ${product.name} to cart`, 'success');
      }
    };

    const updateCartQty = (productId, delta) => {
      const item = cart.value.find(i => i.id === productId);
      if (!item) return;
      item.quantity += delta;
      if (item.quantity <= 0) {
        cart.value = cart.value.filter(i => i.id !== productId);
      }
    };

    const cartSubtotal = computed(() => {
      return cart.value.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    });

    const cartItemCount = computed(() => {
      return cart.value.reduce((acc, i) => acc + i.quantity, 0);
    });

    const shippingFee = computed(() => {
      if (cart.value.length === 0) return 0;
      return cartSubtotal.value > 100 ? 0 : 9.99;
    });

    const discountAmount = computed(() => {
      if (!appliedCoupon.value) return 0;
      const calc = (cartSubtotal.value * appliedCoupon.value.discount_percent) / 100;
      return Math.min(calc, appliedCoupon.value.max_discount || 100);
    });

    const cartTotal = computed(() => {
      const net = cartSubtotal.value - discountAmount.value + shippingFee.value;
      return Math.max(0, net);
    });

    const applyPromoCoupon = async () => {
      if (!couponCode.value.trim()) return;
      try {
        const res = await fetch('/api/ecommerce/validate-coupon', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code: couponCode.value, subtotal: cartSubtotal.value })
        });
        const data = await res.json();
        if (data.success) {
          appliedCoupon.value = data;
          showToast(data.message, 'success');
        } else {
          appliedCoupon.value = null;
          showToast(data.message, 'error');
        }
      } catch (err) {
        showToast('Coupon check failed: ' + err.message, 'error');
      }
    };

    const submitEcommerceCheckout = async () => {
      if (cart.value.length === 0) {
        showToast('Your shopping cart is empty.', 'error');
        return;
      }
      isCheckingOut.value = true;
      try {
        const payload = {
          customer_name: customerForm.value.name,
          customer_email: customerForm.value.email,
          shipping_address: customerForm.value.address,
          payment_method: customerForm.value.paymentMethod,
          coupon_code: appliedCoupon.value ? appliedCoupon.value.code : '',
          items: cart.value.map(i => ({ id: i.id, name: i.name, price: i.price, quantity: i.quantity }))
        };

        const res = await fetch('/api/ecommerce/checkout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.success) {
          confirmedOrderModal.value = {
            orderNumber: data.adapter_result.order_number,
            transactionId: data.transaction_id,
            amount: data.amount,
            fee: data.fee,
            items: [...cart.value],
            customerName: customerForm.value.name,
            shippingAddress: customerForm.value.address,
            deliveryEstimate: data.adapter_result.delivery_estimate
          };
          cart.value = [];
          showToast(`Order ${data.adapter_result.order_number} confirmed via Reusable Payment Service!`, 'success');
          loadProducts();
          loadOrdersHistory();
          loadTelemetry();
        } else {
          showToast(data.error || 'Checkout failed.', 'error');
        }
      } catch (err) {
        showToast('Checkout communication error: ' + err.message, 'error');
      } finally {
        isCheckingOut.value = false;
      }
    };

    // =========================================================================
    // 2. BANKING CLIENT (Apex Bank) STATE & ACTIONS
    // =========================================================================
    const bankingAccounts = ref([]);
    const beneficiaries = ref([]);
    const bankingStatement = ref([]);
    const isTransferring = ref(false);
    const transferSpeed = ref('IMPS');
    const selectedSourceAccount = ref('');
    const transferForm = ref({
      beneficiaryAccount: '',
      beneficiaryName: '',
      amount: 650.00, // Pre-filled >= 500 to immediately demonstrate 2FA OTP capability
      memo: 'Consulting Retainer Payment'
    });

    const otpModal = ref({
      show: false,
      txId: null,
      otpCodeHint: '',
      enteredOtp: '',
      isVerifying: false
    });

    const loadBankingData = async () => {
      try {
        const [accRes, benRes, stmtRes] = await Promise.all([
          fetch('/api/banking/accounts'),
          fetch('/api/banking/beneficiaries'),
          fetch('/api/banking/statement')
        ]);
        const accData = await accRes.json();
        const benData = await benRes.json();
        const stmtData = await stmtRes.json();

        if (accData.success) {
          bankingAccounts.value = accData.accounts;
          if (bankingAccounts.value.length > 0 && !selectedSourceAccount.value) {
            selectedSourceAccount.value = bankingAccounts.value[0].account_number;
          }
        }
        if (benData.success) {
          beneficiaries.value = benData.beneficiaries;
          if (beneficiaries.value.length > 0 && !transferForm.value.beneficiaryAccount) {
            selectBeneficiary(beneficiaries.value[0]);
          }
        }
        if (stmtData.success) {
          bankingStatement.value = stmtData.statement;
        }
      } catch (err) {
        showToast('Failed to load banking records: ' + err.message, 'error');
      }
    };

    const selectBeneficiary = (ben) => {
      transferForm.value.beneficiaryAccount = ben.beneficiary_account;
      transferForm.value.beneficiaryName = ben.beneficiary_name;
    };

    const calculatedWireFee = computed(() => {
      if (transferSpeed.value === 'WIRE') return 15.00;
      if (transferSpeed.value === 'EXPRESS') return 3.50;
      return 0.50; // IMPS / ACH
    });

    const submitBankingTransfer = async () => {
      if (!selectedSourceAccount.value || !transferForm.value.beneficiaryAccount) {
        showToast('Please select valid sender and recipient accounts.', 'error');
        return;
      }
      if (transferForm.value.amount <= 0) {
        showToast('Transfer amount must be greater than zero.', 'error');
        return;
      }

      isTransferring.value = true;
      try {
        const payload = {
          source_account: selectedSourceAccount.value,
          target_account: transferForm.value.beneficiaryAccount,
          beneficiary_name: transferForm.value.beneficiaryName,
          amount: parseFloat(transferForm.value.amount),
          transfer_speed: transferSpeed.value,
          memo: transferForm.value.memo
        };

        const res = await fetch('/api/banking/transfer', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.success) {
          if (data.requires_otp) {
            // High-value transfer triggered 2FA challenge!
            otpModal.value = {
              show: true,
              txId: data.transaction_id,
              otpCodeHint: data.otp_challenge_hint,
              enteredOtp: '',
              isVerifying: false
            };
            showToast('High-security transaction requires 2-Factor OTP verification.', 'info');
          } else {
            showToast(`Transfer Settled: ${data.adapter_result.transfer_reference}`, 'success');
            loadBankingData();
            loadTelemetry();
          }
        } else {
          showToast(data.error || 'Transfer declined by enterprise payment policy.', 'error');
        }
      } catch (err) {
        showToast('Banking service error: ' + err.message, 'error');
      } finally {
        isTransferring.value = false;
      }
    };

    const verifyOtpPasscode = async () => {
      if (!otpModal.value.enteredOtp.trim()) {
        showToast('Please enter the 6-digit OTP passcode.', 'error');
        return;
      }
      otpModal.value.isVerifying = true;
      try {
        const res = await fetch('/api/banking/verify-otp', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            transaction_id: otpModal.value.txId,
            otp_code: otpModal.value.enteredOtp.trim()
          })
        });
        const data = await res.json();
        if (data.success) {
          showToast(`Security verification passed! Funds transferred.`, 'success');
          otpModal.value.show = false;
          loadBankingData();
          loadTelemetry();
        } else {
          showToast(data.error || 'Invalid OTP code.', 'error');
        }
      } catch (err) {
        showToast('Verification error: ' + err.message, 'error');
      } finally {
        otpModal.value.isVerifying = false;
      }
    };

    // =========================================================================
    // 3. SOA CONTROL CENTER & TELEMETRY (TASK 3 SHOWCASE)
    // =========================================================================
    const soaDefinition = ref(null);
    const telemetry = ref({
      total_transactions: 0,
      total_volume: 0,
      avg_risk_score: 0,
      avg_latency_ms: 12.4,
      sla_uptime_percent: 99.98,
      app_distribution: {
        ecommerce: { count: 0, volume: 0 },
        banking: { count: 0, volume: 0 }
      },
      recent_transactions: [],
      recent_traces: []
    });
    const selectedContractModal = ref(null);

    const loadSoaDefinition = async () => {
      try {
        const res = await fetch('/api/soa/definition');
        const data = await res.json();
        soaDefinition.value = data;
      } catch (err) {
        console.error(err);
      }
    };

    const loadTelemetry = async () => {
      try {
        const res = await fetch('/api/soa/telemetry');
        const data = await res.json();
        telemetry.value = data;
      } catch (err) {
        console.error(err);
      }
    };

    const resetDemo = async () => {
      try {
        const res = await fetch('/api/soa/reset-demo', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          showToast('Demo environment reset successfully! Ready for presentation.', 'success');
          loadProducts();
          loadBankingData();
          loadOrdersHistory();
          loadTelemetry();
        }
      } catch (err) {
        showToast('Reset failed: ' + err.message, 'error');
      }
    };

    const inspectTrace = (trace) => {
      selectedContractModal.value = trace;
    };

    onMounted(() => {
      loadProducts();
      loadBankingData();
      loadOrdersHistory();
      loadSoaDefinition();
      loadTelemetry();
    });

    return {
      activeTab,
      toasts,
      showToast,

      // E-Commerce
      products,
      cart,
      cartItemCount,
      couponCode,
      appliedCoupon,
      isCheckingOut,
      confirmedOrderModal,
      ordersHistory,
      customerForm,
      addToCart,
      updateCartQty,
      cartSubtotal,
      shippingFee,
      discountAmount,
      cartTotal,
      applyPromoCoupon,
      submitEcommerceCheckout,

      // Banking
      bankingAccounts,
      beneficiaries,
      bankingStatement,
      isTransferring,
      transferSpeed,
      selectedSourceAccount,
      transferForm,
      otpModal,
      selectBeneficiary,
      calculatedWireFee,
      submitBankingTransfer,
      verifyOtpPasscode,

      // SOA
      soaDefinition,
      telemetry,
      selectedContractModal,
      resetDemo,
      inspectTrace
    };
  }
}).mount('#app');
