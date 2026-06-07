import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

// ========== API URL - CHANGE THIS FOR PRODUCTION ==========
// For local development: http://localhost:8000/api
// For production: https://senti-invest.onrender.com/api
const API_URL = 'https://senti-invest.onrender.com/api';

function App() {
  // ========== PAGE STATES ==========
  const [showLogin, setShowLogin] = useState(true);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [userId, setUserId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('');
  
  // ========== LOGIN FORM ==========
  const [loginPhone, setLoginPhone] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  
  // ========== SIGNUP FORM ==========
  const [signupPhone, setSignupPhone] = useState('');
  const [signupPassword, setSignupPassword] = useState('');
  const [signupConfirmPassword, setSignupConfirmPassword] = useState('');
  const [signupName, setSignupName] = useState('');
  const [referralCodeFromUrl, setReferralCodeFromUrl] = useState('');
  
  // ========== DASHBOARD STATE ==========
  const [balance, setBalance] = useState(0);
  const [totalDeposited, setTotalDeposited] = useState(0);
  const [totalWithdrawn, setTotalWithdrawn] = useState(0);
  const [totalEarned, setTotalEarned] = useState(0);
  const [dailyEarnings, setDailyEarnings] = useState(0);
  const [activeInvestments, setActiveInvestments] = useState([]);
  
  // ========== PRODUCTS STATE ==========
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [investAmount, setInvestAmount] = useState('');
  
  // ========== UPGRADE MODAL STATE ==========
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [upgradingInvestment, setUpgradingInvestment] = useState(null);
  const [availableUpgradeProducts, setAvailableUpgradeProducts] = useState([]);
  const [selectedUpgradeProduct, setSelectedUpgradeProduct] = useState(null);
  
  // ========== DEPOSIT STATE ==========
  const [depositAmount, setDepositAmount] = useState('');
  const [mpesaPhone, setMpesaPhone] = useState('');
  const [mpesaMessage, setMpesaMessage] = useState('');
  
  // ========== WITHDRAWAL STATE ==========
  const [withdrawAmount, setWithdrawAmount] = useState('');
  const [withdrawPhone, setWithdrawPhone] = useState('');
  const [withdrawalHistory, setWithdrawalHistory] = useState([]);
  const [showWithdrawalHistory, setShowWithdrawalHistory] = useState(true);
  
  // ========== REFERRAL STATE ==========
  const [referralLink, setReferralLink] = useState('');
  const [referralCode, setReferralCode] = useState('');
  const [referralCount, setReferralCount] = useState(0);
  const [pendingBonuses, setPendingBonuses] = useState([]);
  const [pendingBonusTotal, setPendingBonusTotal] = useState(0);
  const [claimedBonusTotal, setClaimedBonusTotal] = useState(0);
  const [referralList, setReferralList] = useState({ qualified: [], invested: [], deposited: [], pending: [] });
  const [bonusHistory, setBonusHistory] = useState([]);
  
  // ========== CURRENT PAGE ==========
  const [currentPage, setCurrentPage] = useState('dashboard');

  // ========== GET REFERRAL CODE FROM URL ON MOUNT ==========
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ref = params.get('ref');
    if (ref) {
      setReferralCodeFromUrl(ref);
      console.log("📢 Referral code from URL:", ref);
    }
  }, []);

  // ========== HELPER FUNCTIONS ==========
  const formatCurrency = (amount) => {
    return `KES ${amount.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  };

  const getLevelColor = (level) => {
    const colors = {
      'bronze': '#cd7f32',
      'silver': '#c0c0c0',
      'gold': '#ffd700',
      'platinum': '#e5e4e2',
      'diamond': '#b9f2ff',
      'vip': '#ff0066'
    };
    return colors[level] || '#666';
  };

  const getStatusIcon = (status) => {
    switch(status) {
      case 'pending': return '⏳';
      case 'approved': return '✅';
      case 'rejected': return '❌';
      default: return '📋';
    }
  };

  const getStatusText = (status) => {
    switch(status) {
      case 'pending': return 'Pending';
      case 'approved': return 'Approved';
      case 'rejected': return 'Rejected';
      default: return status;
    }
  };

  const getStatusNote = (status) => {
    switch(status) {
      case 'pending': return 'Waiting for admin approval';
      case 'approved': return 'Money sent to your M-Pesa';
      case 'rejected': return 'Contact support for assistance';
      default: return '';
    }
  };

  const showMessage = (text, type) => {
    setMessage(text);
    setMessageType(type);
    setTimeout(() => setMessage(''), 5000);
  };

  // ========== OPEN UPGRADE MODAL ==========
  const openUpgradeModal = (investment) => {
    // Find products with higher investment amount than current
    const higherProducts = products.filter(p => 
      !p.locked && p.min_investment > investment.amount
    ).sort((a, b) => a.min_investment - b.min_investment);
    
    setAvailableUpgradeProducts(higherProducts);
    setUpgradingInvestment(investment);
    setSelectedUpgradeProduct(null);
    setShowUpgradeModal(true);
  };

  // ========== HANDLE UPGRADE ==========
  const handleUpgrade = async () => {
    if (!selectedUpgradeProduct || !upgradingInvestment) return;
    
    setIsLoading(true);
    try {
      const response = await axios.post(`${API_URL}/upgrade-investment/`, {
        user_id: userId,
        investment_id: upgradingInvestment.id,
        new_product_id: selectedUpgradeProduct.id
      });
      
      if (response.data.success) {
        showMessage(response.data.message, 'success');
        setShowUpgradeModal(false);
        setUpgradingInvestment(null);
        setSelectedUpgradeProduct(null);
        await loadDashboardData(userId);
      } else {
        showMessage(response.data.error || 'Upgrade failed', 'error');
      }
    } catch (error) {
      showMessage(error.response?.data?.error || 'Upgrade failed', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  // ========== LOAD REFERRAL LIST WITH STATUS ==========
  const loadReferralListWithStatus = async (id) => {
    try {
      const response = await axios.get(`${API_URL}/referral-list-status/?user_id=${id}`);
      if (response.data.success) {
        setReferralList(response.data.referrals);
      }
    } catch (error) {
      console.error('Failed to load referral list:', error);
    }
  };

  // ========== LOAD BONUS HISTORY ==========
  const loadBonusHistory = async (id) => {
    try {
      const response = await axios.get(`${API_URL}/bonus-history/?user_id=${id}`);
      if (response.data.success) {
        setBonusHistory(response.data.history);
      }
    } catch (error) {
      console.error('Failed to load bonus history:', error);
    }
  };

  // ========== LOAD WITHDRAWAL HISTORY ==========
  const loadWithdrawalHistory = async (id) => {
    try {
      const response = await axios.get(`${API_URL}/withdrawal-history/?user_id=${id}`);
      if (response.data.success) {
        setWithdrawalHistory(response.data.withdrawals);
      }
    } catch (error) {
      console.error('Failed to load withdrawal history:', error);
    }
  };

  // ========== LOAD INVESTMENTS DATA ==========
  const loadInvestmentsData = async (id) => {
    try {
      console.log("🔄 Loading investments for user:", id);
      const invRes = await axios.get(`${API_URL}/my-investments/?user_id=${id}`);
      if (invRes.data.success) {
        setActiveInvestments(invRes.data.investments || []);
        setDailyEarnings(invRes.data.total_daily_earnings || 0);
      } else {
        setActiveInvestments([]);
        setDailyEarnings(0);
      }
    } catch (error) {
      console.error('❌ Failed to load investments:', error);
      setActiveInvestments([]);
      setDailyEarnings(0);
    }
  };

  // ========== LOAD USER DATA ==========
  useEffect(() => {
    const savedUserId = localStorage.getItem('userId');
    if (savedUserId) {
      setUserId(savedUserId);
      setIsLoggedIn(true);
      loadDashboardData(savedUserId);
      loadProducts();
      loadReferralInfo(savedUserId);
      loadWithdrawalHistory(savedUserId);
      loadReferralListWithStatus(savedUserId);
      loadBonusHistory(savedUserId);
      checkAccountStatus(savedUserId);
    }
  }, []);

  const checkAccountStatus = async (id) => {
    try {
      const response = await axios.get(`${API_URL}/check-account-status/?user_id=${id}`);
      if (response.data.is_banned) {
        showMessage('Your account has been banned. Contact admin.', 'error');
        handleLogout();
      } else if (response.data.is_frozen) {
        showMessage('Your account is frozen. Contact admin.', 'error');
        handleLogout();
      }
    } catch (error) {
      console.error('Failed to check account status:', error);
    }
  };

  const loadDashboardData = async (id) => {
    try {
      console.log("📊 Loading dashboard for user:", id);
      
      const walletRes = await axios.get(`${API_URL}/wallet/?user_id=${id}`);
      setBalance(walletRes.data.balance || 0);
      setTotalDeposited(walletRes.data.total_deposited || 0);
      setTotalWithdrawn(walletRes.data.total_withdrawn || 0);
      setTotalEarned(walletRes.data.total_earned || 0);
      
      await loadInvestmentsData(id);
      
    } catch (error) {
      console.error('Failed to load dashboard:', error);
    }
  };

  const loadProducts = async () => {
    const productList = [
      { id: 1, name: 'Micro Starter', min_investment: 100, daily_earnings: 4, level: 'bronze', duration_days: 25, locked: false },
      { id: 2, name: 'Micro Plus', min_investment: 150, daily_earnings: 6, level: 'bronze', duration_days: 25, locked: false },
      { id: 3, name: 'Bronze Micro', min_investment: 200, daily_earnings: 8, level: 'bronze', duration_days: 25, locked: false },
      { id: 4, name: 'Bronze Standard', min_investment: 300, daily_earnings: 12, level: 'bronze', duration_days: 25, locked: false },
      { id: 5, name: 'Bronze Plus', min_investment: 400, daily_earnings: 16, level: 'bronze', duration_days: 25, locked: false },
      { id: 6, name: 'Starter Pack', min_investment: 520, daily_earnings: 21, level: 'bronze', duration_days: 25, locked: false },
      { id: 7, name: 'Bronze Fund', min_investment: 800, daily_earnings: 32, level: 'bronze', duration_days: 25, locked: false },
      { id: 8, name: 'Silver Starter', min_investment: 1000, daily_earnings: 67, level: 'silver', duration_days: 15, locked: false },
      { id: 9, name: 'Silver Plus', min_investment: 1500, daily_earnings: 100, level: 'silver', duration_days: 15, locked: false },
      { id: 10, name: 'Gold Basic', min_investment: 2000, daily_earnings: 133, level: 'gold', duration_days: 15, locked: false },
      { id: 11, name: 'Gold Pro', min_investment: 3000, daily_earnings: 200, level: 'gold', duration_days: 15, locked: false },
      { id: 12, name: 'Platinum Entry', min_investment: 5000, daily_earnings: 500, level: 'platinum', duration_days: 10, locked: false },
      { id: 13, name: 'Platinum Plus', min_investment: 8000, daily_earnings: 800, level: 'platinum', duration_days: 10, locked: false },
      { id: 14, name: 'Diamond Basic', min_investment: 10000, daily_earnings: 1000, level: 'diamond', duration_days: 10, locked: false },
      { id: 15, name: 'Diamond Pro', min_investment: 12000, daily_earnings: 1200, level: 'diamond', duration_days: 10, locked: false },
      { id: 16, name: 'VIP Basic', min_investment: 15000, daily_earnings: 1500, level: 'vip', duration_days: 10, locked: false },
      { id: 17, name: 'VIP Plus', min_investment: 20000, daily_earnings: 2000, level: 'vip', duration_days: 10, locked: false },
      { id: 18, name: 'VIP Elite', min_investment: 30000, daily_earnings: 6000, level: 'vip', duration_days: 5, locked: true },
      { id: 19, name: 'VIP Premium', min_investment: 50000, daily_earnings: 10000, level: 'vip', duration_days: 5, locked: true },
      { id: 20, name: 'VIP Ultimate', min_investment: 70000, daily_earnings: 14000, level: 'vip', duration_days: 5, locked: true },
      { id: 21, name: 'VIP Diamond', min_investment: 100000, daily_earnings: 20000, level: 'vip', duration_days: 5, locked: true },
    ];
    setProducts(productList);
  };

  const loadReferralInfo = async (id) => {
    try {
      const response = await axios.get(`${API_URL}/referral-info/?user_id=${id}`);
      if (response.data.success) {
        setReferralLink(response.data.referral_link);
        setReferralCode(response.data.referral_code);
        setReferralCount(response.data.referral_count);
        setPendingBonuses(response.data.pending_bonuses);
        setPendingBonusTotal(response.data.pending_total);
        setClaimedBonusTotal(response.data.claimed_total);
      }
    } catch (error) {
      console.error('Failed to load referral info:', error);
    }
  };

  const claimBonus = async (bonusId) => {
    setIsLoading(true);
    try {
      const response = await axios.post(`${API_URL}/claim-bonus/`, {
        user_id: userId,
        bonus_id: bonusId
      });
      if (response.data.success) {
        showMessage(response.data.message, 'success');
        await loadDashboardData(userId);
        await loadReferralInfo(userId);
        await loadBonusHistory(userId);
        await loadReferralListWithStatus(userId);
      }
    } catch (error) {
      showMessage(error.response?.data?.error || 'Failed to claim bonus', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const copyReferralLink = () => {
    navigator.clipboard.writeText(referralLink);
    showMessage('Referral link copied!', 'success');
  };

  // ========== MANUAL PAYMENT ==========
  const processManualPayment = async () => {
    const amount = parseFloat(depositAmount);
    if (!amount || amount < 100) {
      showMessage(`Minimum deposit is ${formatCurrency(100)}`, 'error');
      return;
    }
    if (!mpesaMessage || mpesaMessage.length < 20) {
      showMessage('Please paste your M-Pesa confirmation message', 'error');
      return;
    }
    setIsLoading(true);
    try {
      const response = await axios.post(`${API_URL}/verify-manual-payment/`, {
        user_id: userId,
        amount: amount,
        phone_number: mpesaPhone,
        mpesa_message: mpesaMessage
      });
      if (response.data.success) {
        showMessage(response.data.message, 'success');
        setDepositAmount('');
        setMpesaMessage('');
        setMpesaPhone('');
        loadDashboardData(userId);
      } else {
        showMessage(response.data.error || 'Verification failed', 'error');
      }
    } catch (error) {
      showMessage(error.response?.data?.error || 'Verification failed', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  // ========== SIGNUP ==========
  const handleSignup = async () => {
    if (!signupPhone) {
      showMessage('Please enter phone number', 'error');
      return;
    }
    if (!signupPassword) {
      showMessage('Please enter password', 'error');
      return;
    }
    if (signupPassword !== signupConfirmPassword) {
      showMessage('Passwords do not match', 'error');
      return;
    }
    if (signupPassword.length < 4) {
      showMessage('Password must be at least 4 characters', 'error');
      return;
    }
    
    setIsLoading(true);
    try {
      const response = await axios.post(`${API_URL}/signup/`, {
        phone_number: signupPhone,
        password: signupPassword,
        full_name: signupName,
        referral_code: referralCodeFromUrl
      });
      
      if (response.data.success) {
        showMessage('Account created! Awaiting admin approval.', 'success');
        setSignupPhone('');
        setSignupPassword('');
        setSignupConfirmPassword('');
        setSignupName('');
        setShowLogin(true);
      }
    } catch (error) {
      showMessage(error.response?.data?.error || 'Signup failed', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  // ========== LOGIN ==========
  const handleLogin = async () => {
    if (!loginPhone) {
      showMessage('Please enter phone number', 'error');
      return;
    }
    if (!loginPassword) {
      showMessage('Please enter password', 'error');
      return;
    }
    
    setIsLoading(true);
    try {
      const response = await axios.post(`${API_URL}/login/`, {
        phone_number: loginPhone,
        password: loginPassword
      });
      
      if (response.data.success) {
        setUserId(response.data.user_id);
        setIsLoggedIn(true);
        localStorage.setItem('userId', response.data.user_id);
        showMessage('Login successful!', 'success');
        await loadDashboardData(response.data.user_id);
        await loadReferralInfo(response.data.user_id);
        await loadWithdrawalHistory(response.data.user_id);
        await loadReferralListWithStatus(response.data.user_id);
        await loadBonusHistory(response.data.user_id);
        setCurrentPage('dashboard');
      }
    } catch (error) {
      if (error.response?.status === 404) {
        showMessage('Account not found. Please sign up first.', 'error');
      } else if (error.response?.status === 401) {
        showMessage('Invalid password. Please try again.', 'error');
      } else if (error.response?.status === 403) {
        if (error.response?.data?.pending_approval) {
          showMessage('Account pending admin approval. Please wait.', 'info');
        } else {
          showMessage(error.response?.data?.error || 'Account access denied.', 'error');
        }
      } else {
        showMessage('Login failed. Please try again.', 'error');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // ========== WITHDRAWAL ==========
  const handleWithdraw = async () => {
    const amount = parseFloat(withdrawAmount);
    if (!amount || amount < 300) {
      showMessage(`Minimum withdrawal is ${formatCurrency(300)}`, 'error');
      return;
    }
    if (!withdrawPhone) {
      showMessage('Please enter M-Pesa phone number', 'error');
      return;
    }
    if (amount > balance) {
      showMessage('Insufficient balance', 'error');
      return;
    }
    setIsLoading(true);
    try {
      const response = await axios.post(`${API_URL}/withdraw/`, {
        user_id: userId,
        amount: amount,
        phone_number: withdrawPhone
      });
      if (response.data.success) {
        showMessage(`Withdrawal request submitted for ${formatCurrency(amount)}!`, 'success');
        setWithdrawAmount('');
        setWithdrawPhone('');
        loadDashboardData(userId);
        loadWithdrawalHistory(userId);
      }
    } catch (error) {
      showMessage(error.response?.data?.error || 'Withdrawal failed', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  // ========== INVESTMENT ==========
  const handleInvest = async () => {
    if (!selectedProduct) return;
    
    if (selectedProduct.locked) {
      showMessage(`🔒 ${selectedProduct.name} is coming soon!`, 'info');
      return;
    }
    
    const amount = parseFloat(investAmount);
    if (!amount || amount !== selectedProduct.min_investment) {
      showMessage(`Investment amount must be exactly ${formatCurrency(selectedProduct.min_investment)}`, 'error');
      return;
    }
    if (amount > balance) {
      showMessage(`Insufficient balance. Current: ${formatCurrency(balance)}`, 'error');
      return;
    }
    setIsLoading(true);
    try {
      const response = await axios.post(`${API_URL}/invest/`, {
        user_id: userId,
        product_id: selectedProduct.id,
        amount: amount
      });
      if (response.data.success) {
        showMessage(response.data.message, 'success');
        setSelectedProduct(null);
        setInvestAmount('');
        await loadDashboardData(userId);
        await loadReferralListWithStatus(userId);
        setCurrentPage('investments');
      }
    } catch (error) {
      console.error('Investment error:', error);
      showMessage(error.response?.data?.error || 'Investment failed', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    setUserId(null);
    setIsLoggedIn(false);
    localStorage.removeItem('userId');
    setLoginPhone('');
    setLoginPassword('');
    setCurrentPage('dashboard');
    setActiveInvestments([]);
    setDailyEarnings(0);
    showMessage('Logged out successfully', 'success');
  };

  // ========== LOGIN PAGE ==========
  if (!isLoggedIn && showLogin) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <div className="auth-icon">💰</div>
          <h1 className="auth-title">Senti Earn</h1>
          <p className="auth-subtitle">Welcome back!</p>
          
          <input
            type="tel"
            placeholder="Phone Number"
            className="auth-input"
            value={loginPhone}
            onChange={(e) => setLoginPhone(e.target.value)}
          />
          
          <input
            type="password"
            placeholder="Password"
            className="auth-input"
            value={loginPassword}
            onChange={(e) => setLoginPassword(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleLogin()}
          />
          
          <button className="auth-btn login-btn" onClick={handleLogin} disabled={isLoading}>
            {isLoading ? 'Please wait...' : 'Login'}
          </button>
          
          <p className="auth-switch">
            Don't have an account?{' '}
            <button onClick={() => setShowLogin(false)}>Sign Up</button>
          </p>
          
          {message && <div className={`auth-message ${messageType}`}>{message}</div>}
        </div>
      </div>
    );
  }

  // ========== SIGNUP PAGE ==========
  if (!isLoggedIn && !showLogin) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <div className="auth-icon">📝</div>
          <h1 className="auth-title">Senti Earn</h1>
          <p className="auth-subtitle">Create your account</p>
          
          {referralCodeFromUrl && (
            <div className="referral-notice">
              <p>🎉 You were referred by a friend!</p>
            </div>
          )}
          
          <input type="text" placeholder="Full Name (Optional)" className="auth-input" value={signupName} onChange={(e) => setSignupName(e.target.value)} />
          <input type="tel" placeholder="Phone Number *" className="auth-input" value={signupPhone} onChange={(e) => setSignupPhone(e.target.value)} />
          <input type="password" placeholder="Password *" className="auth-input" value={signupPassword} onChange={(e) => setSignupPassword(e.target.value)} />
          <input type="password" placeholder="Confirm Password *" className="auth-input" value={signupConfirmPassword} onChange={(e) => setSignupConfirmPassword(e.target.value)} />
          
          <button className="auth-btn signup-btn" onClick={handleSignup} disabled={isLoading}>
            {isLoading ? 'Creating...' : 'Sign Up'}
          </button>
          
          <p className="auth-switch">Already have an account? <button onClick={() => setShowLogin(true)}>Login</button></p>
          {message && <div className={`auth-message ${messageType}`}>{message}</div>}
        </div>
      </div>
    );
  }

  // ========== DASHBOARD PAGE ==========
  return (
    <div className="app-container">
      <nav className="navbar">
        <div className="nav-brand">💰 Senti Earn</div>
        <div className="nav-menu">
          <button className={`nav-item ${currentPage === 'dashboard' ? 'active' : ''}`} onClick={() => setCurrentPage('dashboard')}>Dashboard</button>
          <button className={`nav-item ${currentPage === 'products' ? 'active' : ''}`} onClick={() => setCurrentPage('products')}>Products</button>
          <button className={`nav-item ${currentPage === 'investments' ? 'active' : ''}`} onClick={() => { setCurrentPage('investments'); loadInvestmentsData(userId); }}>Investments</button>
          <button className={`nav-item ${currentPage === 'deposit' ? 'active' : ''}`} onClick={() => setCurrentPage('deposit')}>Deposit</button>
          <button className={`nav-item ${currentPage === 'withdraw' ? 'active' : ''}`} onClick={() => setCurrentPage('withdraw')}>Withdraw</button>
          <button className={`nav-item ${currentPage === 'referrals' ? 'active' : ''}`} onClick={() => { setCurrentPage('referrals'); loadReferralInfo(userId); loadReferralListWithStatus(userId); loadBonusHistory(userId); }}>Referrals</button>
          <button className="logout-btn" onClick={handleLogout}>Logout</button>
        </div>
      </nav>

      <div className="main-content">
        {/* Dashboard */}
        {currentPage === 'dashboard' && (
          <>
            <div className="balance-card">
              <p className="balance-label">Total Balance</p>
              <p className="balance-amount">{formatCurrency(balance)}</p>
            </div>
            <div className="stats-grid">
              <div className="stat-card"><p className="stat-label">Total Deposited</p><p className="stat-value">{formatCurrency(totalDeposited)}</p></div>
              <div className="stat-card"><p className="stat-label">Total Withdrawn</p><p className="stat-value">{formatCurrency(totalWithdrawn)}</p></div>
              <div className="stat-card"><p className="stat-label">Total Earned</p><p className="stat-value earnings">{formatCurrency(totalEarned)}</p></div>
              <div className="stat-card"><p className="stat-label">Daily Earnings</p><p className="stat-value daily">{formatCurrency(dailyEarnings)}/day</p></div>
            </div>
            
            <div className="section">
              <div className="section-header"><h2>Active Investments</h2><button className="view-all" onClick={() => { setCurrentPage('investments'); loadInvestmentsData(userId); }}>View All →</button></div>
              {activeInvestments.length === 0 ? (
                <div className="empty-state"><p>No active investments yet.</p><button className="btn-primary" onClick={() => setCurrentPage('products')}>Start Investing</button></div>
              ) : (
                <div className="investments-preview">
                  {activeInvestments.slice(0, 3).map(inv => (
                    <div key={inv.id} className="investment-card-small">
                      <div className="investment-header"><span className="investment-name">{inv.product_name}</span><span className="investment-level" style={{ color: getLevelColor(inv.product_level?.toLowerCase()) }}>{inv.product_level}</span></div>
                      <div className="investment-details"><span>Amount: {formatCurrency(inv.amount)}</span><span>Daily: {formatCurrency(inv.daily_earnings)}</span><span>{inv.days_left} days left</span></div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            <div className="quick-actions">
              <div className="action-card" onClick={() => setCurrentPage('deposit')}><div className="action-icon">💰</div><h3>Deposit</h3><p>Min KES 100</p></div>
              <div className="action-card" onClick={() => setCurrentPage('products')}><div className="action-icon">📈</div><h3>Invest</h3><p>Earn daily</p></div>
              <div className="action-card" onClick={() => setCurrentPage('withdraw')}><div className="action-icon">💸</div><h3>Withdraw</h3><p>Min KES 300</p></div>
            </div>
          </>
        )}

        {/* Products Page */}
        {currentPage === 'products' && (
          <>
            <div className="section-header">
              <h1>Investment Products</h1>
              <p>25 days (100-800) | 15 days (1,000-3,000) | 10 days (5,000-20,000) | 5 days (30,000-100,000 - Coming Soon)</p>
              <p className="coming-soon-note">🔒 Products with lock icon are coming soon - Admin will announce when available</p>
            </div>
            <div className="products-grid">
              {products.map(product => (
                <div 
                  key={product.id} 
                  className={`product-card ${product.locked ? 'product-locked' : ''}`} 
                  onClick={() => !product.locked && setSelectedProduct(product)}
                >
                  {product.locked && (
                    <div className="lock-badge">
                      <span className="lock-icon">🔒</span>
                      <span className="lock-text">Coming Soon</span>
                    </div>
                  )}
                  <div className="product-level" style={{backgroundColor: getLevelColor(product.level)}}>
                    {product.name}
                  </div>
                  <h3 className="product-name">{product.name}</h3>
                  <div className="product-details">
                    <div className="detail"><span className="detail-label">Investment</span><span className="detail-value">{formatCurrency(product.min_investment)}</span></div>
                    <div className="detail"><span className="detail-label">Daily Earnings</span><span className="detail-value highlight">{formatCurrency(product.daily_earnings)}/day</span></div>
                    <div className="detail"><span className="detail-label">Duration</span><span className="detail-value">{product.duration_days} days</span></div>
                  </div>
                  <button className="invest-btn" disabled={product.locked}>
                    {product.locked ? '🔒 Coming Soon' : 'Invest Now →'}
                  </button>
                </div>
              ))}
            </div>

            {selectedProduct && !selectedProduct.locked && (
              <div className="modal-overlay" onClick={() => setSelectedProduct(null)}>
                <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                  <button className="modal-close" onClick={() => setSelectedProduct(null)}>×</button>
                  <h2>Invest in {selectedProduct.name}</h2>
                  <div className="modal-details">
                    <p>💰 Investment: <strong>{formatCurrency(selectedProduct.min_investment)}</strong></p>
                    <p>📈 Daily Return: <strong className="highlight">{formatCurrency(selectedProduct.daily_earnings)}</strong></p>
                    <p>⏱️ Duration: <strong>{selectedProduct.duration_days} days</strong></p>
                    <p>🎯 Total Return: <strong>{formatCurrency(selectedProduct.min_investment * 1.2)}</strong></p>
                    <p>💵 Your Balance: <strong>{formatCurrency(balance)}</strong></p>
                  </div>
                  <input type="number" placeholder={`Enter ${formatCurrency(selectedProduct.min_investment)}`} className="auth-input" value={investAmount} onChange={(e) => setInvestAmount(e.target.value)} />
                  <div className="modal-buttons">
                    <button className="btn-primary" onClick={handleInvest} disabled={isLoading}>{isLoading ? 'Processing...' : 'Confirm'}</button>
                    <button className="btn-secondary" onClick={() => setSelectedProduct(null)}>Cancel</button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* My Investments Page - Updated: Removed Total Earned and Expires, Added Upgrade Button */}
        {currentPage === 'investments' && (
          <>
            <div className="section-header"><h1>My Investments</h1><p>Track your active investments</p></div>
            <div className="daily-summary"><div className="daily-card"><p>Total Daily Earnings</p><h2>{formatCurrency(dailyEarnings)}</h2><small>Earned daily from all investments</small></div></div>
            {isLoading ? (
              <div className="empty-state"><p>Loading investments...</p></div>
            ) : activeInvestments.length === 0 ? (
              <div className="empty-state">
                <p>No active investments yet.</p>
                <button className="btn-primary" onClick={() => setCurrentPage('products')}>Browse Products</button>
              </div>
            ) : (
              <div className="investments-list">
                {activeInvestments.map(inv => (
                  <div key={inv.id} className="investment-card-full">
                    <div className="investment-header">
                      <div>
                        <h3>{inv.product_name}</h3>
                        <span className="level-badge" style={{ background: getLevelColor(inv.product_level?.toLowerCase()) }}>{inv.product_level}</span>
                      </div>
                      <div className="investment-amount">{formatCurrency(inv.amount)}</div>
                    </div>
                    <div className="investment-stats">
                      <div><p className="stat-label">Daily</p><p className="stat-value">{formatCurrency(inv.daily_earnings)}</p></div>
                      <div><p className="stat-label">Days Left</p><p className="stat-value">{inv.days_left}</p></div>
                    </div>
                    <div className="progress-bar"><div className="progress-fill" style={{ width: `${((inv.duration_days - inv.days_left) / inv.duration_days) * 100}%` }}></div></div>
                    {inv.product_level !== 'vip' && (
                      <button 
                        className="upgrade-btn" 
                        onClick={() => openUpgradeModal(inv)}
                      >
                        ⬆️ Upgrade
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* Deposit Page */}
        {currentPage === 'deposit' && (
          <div className="deposit-container">
            <div className="transaction-card">
              <h2>Deposit Funds</h2>
              
              <div className="mpesa-instructions-compact">
                <div className="mpesa-header">
                  <span className="mpesa-icon">📱</span>
                  <span className="mpesa-title">Pay via M-PESA Till: <strong>9315062</strong></span>
                </div>
                <div className="mpesa-steps-compact">
                  <div className="step-compact">1. Open M-PESA → Lipa na M-PESA → Buy Goods</div>
                  <div className="step-compact">2. Enter Till Number: <strong>9315062</strong></div>
                  <div className="step-compact">3. Enter Amount (min KES 100) → Enter PIN → Confirm</div>
                  <div className="step-compact">4. Copy confirmation message & paste below</div>
                </div>
              </div>

              <div className="deposit-form">
                <div className="form-group">
                  <label>Amount (KES) *</label>
                  <input type="number" placeholder="Enter amount (min KES 100)" className="auth-input" value={depositAmount} onChange={(e) => setDepositAmount(e.target.value)} />
                </div>
                <div className="form-group">
                  <label>Your M-Pesa Phone Number *</label>
                  <input type="tel" placeholder="e.g., 0712345678" className="auth-input" value={mpesaPhone} onChange={(e) => setMpesaPhone(e.target.value)} />
                </div>
                <div className="form-group">
                  <label>M-Pesa Confirmation Message *</label>
                  <textarea placeholder="Paste your M-Pesa confirmation message here..." className="auth-input" rows="3" value={mpesaMessage} onChange={(e) => setMpesaMessage(e.target.value)} style={{ resize: 'vertical', fontFamily: 'monospace', fontSize: '12px' }} />
                </div>
                <button className="btn-primary" onClick={processManualPayment} disabled={isLoading}>{isLoading ? 'Processing...' : 'Submit Deposit'}</button>
              </div>
              
              <div className="deposit-notes-compact">
                <span>❌ Fake payments = account ban.</span>
              </div>
            </div>
          </div>
        )}

        {/* Withdraw Page */}
        {currentPage === 'withdraw' && (
          <div className="withdraw-container">
            <div className="transaction-card">
              <h2>Withdraw Funds</h2>
              <div className="withdraw-info-note">
                <p>⏰ <strong>Processing Time:</strong> 1 - 12 hours</p>
                <p>💰 <strong>Minimum Withdrawal:</strong> KES 300</p>
                <p>📱 Funds will be sent to your M-Pesa number after admin approval</p>
              </div>
              <p>Available balance: <strong>{formatCurrency(balance)}</strong></p>
              <input type="number" placeholder="Amount (KES)" className="auth-input" value={withdrawAmount} onChange={(e) => setWithdrawAmount(e.target.value)} />
              <input type="tel" placeholder="M-Pesa Phone Number" className="auth-input" value={withdrawPhone} onChange={(e) => setWithdrawPhone(e.target.value)} />
              <button className="btn-primary" onClick={handleWithdraw} disabled={isLoading}>{isLoading ? 'Processing...' : 'Request Withdrawal'}</button>
            </div>

            <div className="withdrawal-history">
              <div className="history-header" onClick={() => setShowWithdrawalHistory(!showWithdrawalHistory)}>
                <h3>📋 Withdrawal History</h3>
                <span className={`history-toggle ${showWithdrawalHistory ? 'open' : ''}`}>▼</span>
              </div>
              
              {showWithdrawalHistory && (
                <div className="history-list">
                  {withdrawalHistory.length === 0 ? (
                    <div className="empty-history">
                      <p>No withdrawal requests yet.</p>
                      <p className="empty-note">Your withdrawal history will appear here</p>
                    </div>
                  ) : (
                    <table className="history-table">
                      <thead>
                        <tr><th>Date</th><th>Amount</th><th>Phone</th><th>Status</th><th>Note</th></tr>
                      </thead>
                      <tbody>
                        {withdrawalHistory.map((withdrawal, index) => (
                          <tr key={withdrawal.id || index} className={`status-${withdrawal.status}`}>
                            <td>{new Date(withdrawal.created_at).toLocaleDateString()}</td>
                            <td>{formatCurrency(withdrawal.amount)}</td>
                            <td>{withdrawal.phone_number}</td>
                            <td className="status-cell"><span className={`status-badge status-${withdrawal.status}`}>{getStatusIcon(withdrawal.status)} {getStatusText(withdrawal.status)}</span></td>
                            <td className="note-cell">{getStatusNote(withdrawal.status)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Referrals Page */}
        {currentPage === 'referrals' && (
          <div className="referral-container">
            <div className="referral-stats">
              <div className="stat-card">
                <p className="stat-label">People Referred</p>
                <p className="stat-value">{referralCount}</p>
                {referralCount >= 5 && (
                  <small className="bonus-qualified">✅ You qualify for a bonus! Admin will add it.</small>
                )}
                {referralCount < 5 && (
                  <small className="bonus-need">Need {5 - referralCount} more qualified referrals (deposit + invest) to get bonus</small>
                )}
              </div>
              <div className="stat-card">
                <p className="stat-label">Pending Bonuses</p>
                <p className="stat-value earnings">{formatCurrency(pendingBonusTotal)}</p>
                {pendingBonusTotal > 0 && (
                  <small className="bonus-action">Click "Claim" below to add to wallet</small>
                )}
              </div>
              <div className="stat-card">
                <p className="stat-label">Total Earned from Referrals</p>
                <p className="stat-value daily">{formatCurrency(claimedBonusTotal)}</p>
              </div>
            </div>

            <div className="referral-link-box">
              <h3>Your Unique Referral Link</h3>
              <div className="copy-link-container">
                <input type="text" value={referralLink} readOnly className="referral-link-input" />
                <button onClick={copyReferralLink} className="copy-btn">📋 Copy Link</button>
              </div>
              <p className="referral-code-info">Your referral code: <strong>{referralCode}</strong></p>
              <p className="referral-note">💡 Share this link with friends. They get a bonus when they deposit AND invest!</p>
            </div>

            <div className="referral-list-box">
              <h3>📋 Your Referrals</h3>
              <div className="referral-stats-summary">
                <span>✅ Qualified: {referralList.qualified?.length || 0}</span>
                <span>💰 Invested: {referralList.invested?.length || 0}</span>
                <span>🏦 Deposited: {referralList.deposited?.length || 0}</span>
                <span>⏳ Pending: {referralList.pending?.length || 0}</span>
              </div>
              
              {referralList.qualified?.length > 0 && (
                <div className="referral-group qualified">
                  <h4>🎯 Qualified for Bonus (Need deposit + invest)</h4>
                  {referralList.qualified.map(ref => (
                    <div key={ref.id} className="referral-item qualified">
                      <span className="referral-phone">{ref.phone}</span>
                      <span className="referral-status qualified">✅ Qualified - Ready for bonus!</span>
                      <span className="referral-date">Joined: {ref.joined_date}</span>
                    </div>
                  ))}
                </div>
              )}
              
              {referralList.invested?.length > 0 && (
                <div className="referral-group invested">
                  <h4>💰 Invested (Bonus already given)</h4>
                  {referralList.invested.map(ref => (
                    <div key={ref.id} className="referral-item invested">
                      <span className="referral-phone">{ref.phone}</span>
                      <span className="referral-status invested">✅ Invested</span>
                      <span className="referral-date">Joined: {ref.joined_date}</span>
                    </div>
                  ))}
                </div>
              )}
              
              {referralList.deposited?.length > 0 && (
                <div className="referral-group deposited">
                  <h4>🏦 Deposited Only</h4>
                  {referralList.deposited.map(ref => (
                    <div key={ref.id} className="referral-item deposited">
                      <span className="referral-phone">{ref.phone}</span>
                      <span className="referral-status deposited">🏦 Deposited</span>
                      <span className="referral-date">Joined: {ref.joined_date}</span>
                    </div>
                  ))}
                </div>
              )}
              
              {referralList.pending?.length > 0 && (
                <div className="referral-group pending">
                  <h4>⏳ Pending (No deposit yet)</h4>
                  {referralList.pending.map(ref => (
                    <div key={ref.id} className="referral-item pending">
                      <span className="referral-phone">{ref.phone}</span>
                      <span className="referral-status pending">⏳ Pending</span>
                      <span className="referral-date">Joined: {ref.joined_date}</span>
                    </div>
                  ))}
                </div>
              )}
              
              {referralCount === 0 && (
                <div className="empty-referral-list">
                  <p>No referrals yet. Share your link to start earning bonuses!</p>
                </div>
              )}
            </div>

            {bonusHistory.length > 0 && (
              <div className="bonus-history-box">
                <h3>🎁 Bonus History</h3>
                <div className="bonus-history-list">
                  {bonusHistory.map(bonus => (
                    <div key={bonus.id} className={`bonus-history-item ${bonus.status}`}>
                      <span className="bonus-amount">{formatCurrency(bonus.amount)}</span>
                      <span className="bonus-referrals">For {bonus.referred_count} referrals</span>
                      <span className="bonus-date">{bonus.status === 'claimed' ? `Claimed: ${bonus.claimed_at}` : `Created: ${bonus.created_at}`}</span>
                      <span className={`bonus-status ${bonus.status}`}>{bonus.status === 'claimed' ? '✅ Claimed' : '⏳ Pending'}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="referral-info-box">
              <h3>🎉 How Referral Bonuses Work</h3>
              <ul>
                <li>Share your unique referral link with friends</li>
                <li>When they sign up using your link, they appear in your referral list</li>
                <li><strong>Bonus requires BOTH deposit AND investment</strong> from the referred user</li>
                <li><strong>Minimum 5 qualified referrals</strong> required to earn a bonus</li>
                <li>Admin reviews qualified referrals and <strong>manually adds bonuses</strong></li>
                <li>When admin adds a bonus, it appears in "Pending Bonuses" below</li>
                <li>Click <strong>"Claim"</strong> to instantly add the bonus to your wallet balance</li>
                <li>Already rewarded referrals appear muted - no double bonuses</li>
              </ul>
            </div>

            {pendingBonuses.length > 0 && (
              <div className="pending-bonuses">
                <h3>🎁 Congratulations! You have pending bonuses!</h3>
                <div className="bonuses-list">
                  {pendingBonuses.map(bonus => (
                    <div key={bonus.id} className="bonus-card">
                      <div className="bonus-info">
                        <span className="bonus-amount">{formatCurrency(bonus.amount)}</span>
                        <span className="bonus-reason">For referring {bonus.referred_count} qualified people</span>
                        <span className="bonus-status pending">⏳ Pending Claim</span>
                      </div>
                      <button className="claim-bonus-btn" onClick={() => claimBonus(bonus.id)} disabled={isLoading}>
                        {isLoading ? 'Processing...' : '💰 Claim Bonus'}
                      </button>
                    </div>
                  ))}
                </div>
                <p className="bonus-message">🎉 Click "Claim Bonus" to add the amount to your wallet immediately!</p>
              </div>
            )}

            {pendingBonuses.length === 0 && referralCount >= 5 && (
              <div className="referral-waiting">
                <div className="waiting-icon">⏳</div>
                <h3>You've reached {referralCount} referrals!</h3>
                <p>Admin has been notified and will add your bonus soon once they verify deposits and investments.</p>
                <p>Check back later to claim your bonus.</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Upgrade Modal */}
      {showUpgradeModal && upgradingInvestment && (
        <div className="modal-overlay" onClick={() => setShowUpgradeModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowUpgradeModal(false)}>×</button>
            <h2>Upgrade Investment</h2>
            <p>Current: <strong>{upgradingInvestment.product_name}</strong> - {formatCurrency(upgradingInvestment.amount)}</p>
            <p>Daily Earnings: {formatCurrency(upgradingInvestment.daily_earnings)}/day</p>
            
            {availableUpgradeProducts.length === 0 ? (
              <p className="no-upgrade">No upgrade options available. You're already at the highest level!</p>
            ) : (
              <>
                <div className="upgrade-options">
                  {availableUpgradeProducts.map(product => {
                    const difference = product.min_investment - upgradingInvestment.amount;
                    const dailyIncrease = product.daily_earnings - upgradingInvestment.daily_earnings;
                    return (
                      <div 
                        key={product.id} 
                        className={`upgrade-option ${selectedUpgradeProduct?.id === product.id ? 'selected' : ''}`}
                        onClick={() => setSelectedUpgradeProduct(product)}
                      >
                        <div className="upgrade-option-header">
                          <span className="upgrade-option-name">{product.name}</span>
                          <span className="upgrade-option-level" style={{ background: getLevelColor(product.level) }}>{product.level}</span>
                        </div>
                        <div className="upgrade-option-details">
                          <span>Amount: {formatCurrency(product.min_investment)}</span>
                          <span>Daily: {formatCurrency(product.daily_earnings)}/day</span>
                        </div>
                        <div className="upgrade-option-cost">
                          <span>Upgrade Cost: {formatCurrency(difference)}</span>
                          <span className="daily-increase">+{formatCurrency(dailyIncrease)}/day</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="modal-buttons">
                  <button 
                    className="btn-primary" 
                    onClick={handleUpgrade} 
                    disabled={!selectedUpgradeProduct || isLoading}
                  >
                    {isLoading ? 'Processing...' : 'Confirm Upgrade'}
                  </button>
                  <button className="btn-secondary" onClick={() => setShowUpgradeModal(false)}>Cancel</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {message && <div className={`toast-message ${messageType}`}>{message}</div>}
    </div>
  );
}

export default App;