/* ============================================
   NARRATIVE AD NETWORK — Brand Dashboard JS
   ============================================ */

(function () {
  'use strict';

  // ——— Configuration ———
  var API_BASE = 'https://drishti-api-blond.vercel.app';
  var API_KEY = 'mn_test_62e9df6e8017487a482b82568de935e02166dce90b3942a4';
  var COMMON_HEADERS = {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
    'User-Agent': 'Mozilla/5.0'
  };

  // ——— State ———
  var DB = {
    brand_id: '',
    brand_name: '',
    brand_color: '#39A596',
    currentView: 'overview',
    campaigns: [],
    products: [],
    analytics: {},
    wallet: { balance: 0, transactions: [] },
    network_settings: {},
    loading: {},
    dateRange: '7d',
    selectedProducts: [],
    charts: {}
  };

  // ——— DOM Refs ———
  var $content;
  var $viewTitle;
  var $breadcrumbView;
  var $userAvatar;

  // ——— Init ———
  function init() {
    $content = document.getElementById('dashboard-content');
    $viewTitle = document.getElementById('header-title');
    $breadcrumbView = document.getElementById('breadcrumb-view');
    $userAvatar = document.getElementById('header-avatar');

    resolveBrandId();
    bindNav();
    bindMobile();
    switchView('overview');
  }

  function resolveBrandId() {
    var meta = document.querySelector('meta[name="brand-id"]');
    if (meta) {
      DB.brand_id = meta.content;
    } else if (window.ShopifyAnalytics && window.ShopifyAnalytics.meta && window.ShopifyAnalytics.meta.product) {
      DB.brand_id = String(window.ShopifyAnalytics.meta.product.id);
    } else if (window.meta && window.meta.product && window.meta.product.vendor) {
      DB.brand_id = window.meta.product.vendor;
    } else {
      DB.brand_id = '1';
    }

    var nameMeta = document.querySelector('meta[name="brand-name"]');
    DB.brand_name = nameMeta ? nameMeta.content : 'Brand';
    DB.brand_color = '#39A596';

    document.documentElement.style.setProperty('--color-primary', DB.brand_color);
  }

  // ——— Navigation ———
  function bindNav() {
    var items = document.querySelectorAll('[data-nav]');
    items.forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.preventDefault();
        var view = this.getAttribute('data-nav');
        switchView(view);
      });
    });
  }

  function bindMobile() {
    var btn = document.getElementById('mobile-menu-btn');
    var overlay = document.getElementById('mobile-overlay');
    var sidebar = document.getElementById('sidebar');

    if (btn) {
      btn.addEventListener('click', function () {
        sidebar.classList.toggle('mobile-open');
        overlay.classList.toggle('active');
      });
    }

    if (overlay) {
      overlay.addEventListener('click', function () {
        sidebar.classList.remove('mobile-open');
        overlay.classList.remove('active');
      });
    }
  }

  function switchView(view) {
    DB.currentView = view;

    document.querySelectorAll('[data-nav]').forEach(function (el) {
      el.classList.toggle('active', el.getAttribute('data-nav') === view);
    });

    var labels = {
      overview: 'Overview',
      campaigns: 'Campaigns',
      products: 'Products',
      settings: 'Network Settings',
      analytics: 'Analytics',
      wallet: 'Billing & Wallet'
    };

    if ($viewTitle) $viewTitle.textContent = labels[view] || view;
    if ($breadcrumbView) $breadcrumbView.textContent = labels[view] || view;

    var sidebar = document.getElementById('sidebar');
    var overlay = document.getElementById('mobile-overlay');
    if (sidebar) sidebar.classList.remove('mobile-open');
    if (overlay) overlay.classList.remove('active');

    $content.innerHTML = '<div class="skeleton skeleton-card" style="height:400px"></div>';

    switch (view) {
      case 'overview': loadOverview(); break;
      case 'campaigns': loadCampaigns(); break;
      case 'products': loadProducts(); break;
      case 'settings': loadNetworkSettings(); break;
      case 'analytics': loadAnalytics(DB.dateRange); break;
      case 'wallet': loadWallet(); break;
      default: loadOverview();
    }
  }

  // ——— API Helper ———
  function dbFetch(path, options) {
    var url = API_BASE + path;
    var opts = {
      method: (options && options.method) || 'GET',
      headers: COMMON_HEADERS
    };
    if (options && options.body) {
      opts.body = JSON.stringify(options.body);
    }
    return fetch(url, opts).then(function (res) {
      if (!res.ok) {
        return res.json().catch(function () { return {}; }).then(function (err) {
          throw new Error(err.message || ('API Error: ' + res.status));
        });
      }
      return res.json();
    });
  }

  // ——— Utilities ———
  function fmtPrice(n) {
    if (n == null) return '\u20B90';
    return '\u20B9' + Number(n).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  }

  function fmtPriceDec(n) {
    if (n == null) return '\u20B90';
    return '\u20B9' + Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function fmtNum(n) {
    if (n == null) return '0';
    return Number(n).toLocaleString('en-IN');
  }

  function fmtDate(d) {
    if (!d) return '-';
    var dt = new Date(d);
    if (isNaN(dt.getTime())) return '-';
    var day = dt.getDate();
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return months[dt.getMonth()] + ' ' + day + ', ' + dt.getFullYear();
  }

  function fmtDateShort(d) {
    if (!d) return '-';
    var dt = new Date(d);
    if (isNaN(dt.getTime())) return '-';
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return months[dt.getMonth()] + ' ' + dt.getDate();
  }

  function toDateInputValue(d) {
    if (!d) return '';
    var dt = new Date(d);
    if (isNaN(dt.getTime())) return '';
    var yyyy = dt.getFullYear();
    var mm = String(dt.getMonth() + 1).padStart(2, '0');
    var dd = String(dt.getDate()).padStart(2, '0');
    return yyyy + '-' + mm + '-' + dd;
  }

  function fmtTimeAgo(d) {
    if (!d) return '';
    var now = Date.now();
    var then = new Date(d).getTime();
    var diff = Math.floor((now - then) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
    return fmtDate(d);
  }

  function truncate(str, len) {
    if (!str) return '';
    return str.length > len ? str.substring(0, len) + '...' : str;
  }

  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  // ——— Toast ———
  function showToast(msg, type) {
    type = type || 'info';
    var existing = document.querySelector('.db-toast');
    if (existing) existing.remove();

    var toast = document.createElement('div');
    toast.className = 'db-toast db-toast--' + type;

    var icon = type === 'success' ? '\u2713' : type === 'error' ? '\u2717' : '\u2139';
    toast.innerHTML = '<span class="db-toast-icon">' + icon + '</span><span class="db-toast-msg">' + escapeHtml(msg) + '</span>';

    Object.assign(toast.style, {
      position: 'fixed',
      bottom: '24px',
      right: '24px',
      padding: '12px 20px',
      borderRadius: '10px',
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      fontSize: '0.875rem',
      fontWeight: '500',
      zIndex: '2000',
      animation: 'fadeSlideUp 0.3s ease both',
      boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      color: '#fff',
      background: type === 'success' ? '#065f46' : type === 'error' ? '#7f1d1d' : '#1e3a5f',
      border: '1px solid ' + (type === 'success' ? '#059669' : type === 'error' ? '#dc2626' : '#3b82f6')
    });

    document.body.appendChild(toast);
    setTimeout(function () {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(function () { toast.remove(); }, 300);
    }, 3500);
  }

  // ——— Confirm ———
  function showConfirm(msg) {
    return new Promise(function (resolve) {
      var overlay = document.createElement('div');
      overlay.className = 'modal-overlay open';

      overlay.innerHTML =
        '<div class="modal" style="max-width:400px">' +
        '  <div class="modal-header">' +
        '    <h3 class="modal-title">Confirm</h3>' +
        '  </div>' +
        '  <div class="modal-body">' +
        '    <p style="color:var(--text-secondary);font-size:var(--font-size-sm);line-height:1.6">' + escapeHtml(msg) + '</p>' +
        '  </div>' +
        '  <div class="modal-footer">' +
        '    <button class="btn btn-ghost" id="confirm-cancel">Cancel</button>' +
        '    <button class="btn btn-danger" id="confirm-ok">Confirm</button>' +
        '  </div>' +
        '</div>';

      document.body.appendChild(overlay);

      overlay.querySelector('#confirm-cancel').addEventListener('click', function () {
        overlay.remove();
        resolve(false);
      });

      overlay.querySelector('#confirm-ok').addEventListener('click', function () {
        overlay.remove();
        resolve(true);
      });

      overlay.addEventListener('click', function (e) {
        if (e.target === overlay) {
          overlay.remove();
          resolve(false);
        }
      });
    });
  }

  // ——— Loading Helpers ———
  function skeletonCardGrid(count) {
    var html = '<div class="stats-grid">';
    for (var i = 0; i < (count || 4); i++) {
      html += '<div class="stat-card"><div class="skeleton skeleton-text" style="width:40%;height:14px;margin-bottom:12px"></div><div class="skeleton skeleton-heading" style="width:60%;height:28px;margin-bottom:8px"></div><div class="skeleton skeleton-text" style="width:30%;height:12px"></div></div>';
    }
    return html + '</div>';
  }

  function skeletonTable(rows) {
    var r = rows || 5;
    var html = '<div class="panel"><div class="skeleton skeleton-heading" style="width:30%"></div>';
    for (var i = 0; i < r; i++) {
      html += '<div class="skeleton skeleton-text" style="height:40px;margin-bottom:4px"></div>';
    }
    return html + '</div>';
  }

  function emptyState(icon, title, text, btnHtml) {
    return '<div class="empty-state">' +
      '<div class="empty-state-icon">' + icon + '</div>' +
      '<h3 class="empty-state-title">' + escapeHtml(title) + '</h3>' +
      '<p class="empty-state-text">' + escapeHtml(text) + '</p>' +
      (btnHtml || '') +
      '</div>';
  }

  // ============================================
  // OVERVIEW
  // ============================================
  function loadOverview() {
    $content.innerHTML = skeletonCardGrid(4);

    dbFetch('/api/network/report?brand_id=' + encodeURIComponent(DB.brand_id))
      .then(function (data) {
        renderOverview(data);
      })
      .catch(function (err) {
        console.error('Overview load error:', err);
        $content.innerHTML =
          skeletonCardGrid(4) +
          '<div class="panel" style="text-align:center;padding:var(--space-3xl)">' +
          '<p class="text-secondary text-sm">Failed to load overview data.</p>' +
          '<button class="btn btn-secondary btn-sm mt-md" onclick="location.reload()">Retry</button>' +
          '</div>';
        showToast('Failed to load overview', 'error');
      });
  }

  function renderOverview(data) {
    var stats = data.stats || data;
    var vton = stats.vton_sessions || stats.vtonSessions || 0;
    var impressions = stats.cross_brand_impressions || stats.impressions || 0;
    var clicks = stats.clicks || 0;
    var revenue = stats.revenue || 0;
    var trendVton = stats.vton_trend || stats.trends?.vton || 0;
    var trendImpressions = stats.impressions_trend || stats.trends?.impressions || 0;
    var trendClicks = stats.clicks_trend || stats.trends?.clicks || 0;
    var trendRevenue = stats.revenue_trend || stats.trends?.revenue || 0;
    var events = data.events || data.activity || [];
    var network = data.network_status || data.networkStatus || {};

    var html = '';

    // Stat cards
    html += '<div class="stats-grid">';
    html += renderStatCard('VTON Sessions', fmtNum(vton), trendVton, '\uD83D\uDC64');
    html += renderStatCard('Cross-brand Impressions', fmtNum(impressions), trendImpressions, '\uD83D\uDCE2');
    html += renderStatCard('Clicks', fmtNum(clicks), trendClicks, '\uD83D\uDD17');
    html += renderStatCard('Revenue', fmtPrice(revenue), trendRevenue, '\uD83D\uDCB0');
    html += '</div>';

    // Two columns: chart + activity
    html += '<div style="display:grid;grid-template-columns:1.5fr 1fr;gap:var(--space-lg);margin-bottom:var(--space-2xl)">';

    // Mini chart
    html += '<div class="panel">' +
      '<div class="panel-header"><span class="panel-title">Last 7 Days</span></div>' +
      '<div style="height:220px;position:relative"><canvas id="overview-mini-chart"></canvas></div>' +
      '</div>';

    // Activity feed
    html += '<div class="panel">' +
      '<div class="panel-header"><span class="panel-title">Recent Activity</span></div>' +
      '<div id="activity-feed">' +
      renderActivityFeed(events) +
      '</div>' +
      '</div>';

    html += '</div>';

    // Network status
    html += '<div class="panel">' +
      '<div class="panel-header"><span class="panel-title">Network Status</span></div>' +
      '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:var(--space-md)">' +
      renderNetworkStatusItem('VTON Enabled', network.vton_enabled || network.vtonEnabled) +
      renderNetworkStatusItem('Recommendations', network.receive_recommendations || network.receiveRecommendations) +
      renderNetworkStatusItem('Product Distribution', network.distribute_products || network.distributeProducts) +
      renderNetworkStatusItem('Promotions', network.promote_products || network.promoteProducts) +
      '</div>' +
      '</div>';

    $content.innerHTML = html;
    renderMiniChart(data.chart_data || data.chartData || generateMockChartData());
  }

  function renderStatCard(label, value, trend, icon) {
    var trendClass = trend >= 0 ? 'up' : 'down';
    var arrow = trend >= 0 ? '\u2191' : '\u2193';
    var trendAbs = Math.abs(trend);

    return '<div class="stat-card">' +
      '<div class="stat-card-header">' +
      '<span class="stat-card-label">' + label + '</span>' +
      '<span class="stat-card-icon">' + icon + '</span>' +
      '</div>' +
      '<div class="stat-card-value">' + value + '</div>' +
      '<span class="stat-card-trend ' + trendClass + '">' +
      '<span class="stat-card-trend-arrow">' + arrow + '</span> ' +
      trendAbs.toFixed(1) + '% vs last period' +
      '</span>' +
      '</div>';
  }

  function renderActivityFeed(events) {
    if (!events || events.length === 0) {
      return '<div style="padding:var(--space-lg);text-align:center;color:var(--text-muted);font-size:var(--font-size-sm)">No recent activity</div>';
    }

    var items = events.slice(0, 10);
    var html = '<div style="max-height:220px;overflow-y:auto">';
    items.forEach(function (evt) {
      var type = evt.type || 'info';
      var iconMap = {
        vton: '\uD83D\uDC64', impression: '\uD83D\uDCE2', click: '\uD83D\uDD17',
        conversion: '\u2705', sale: '\uD83D\uDCB0', campaign: '\uD83D\uDCE3'
      };
      var icon = iconMap[type] || '\u2022';

      html += '<div style="display:flex;align-items:flex-start;gap:var(--space-sm);padding:var(--space-sm) 0;border-bottom:1px solid var(--border-subtle)">' +
        '<span style="font-size:var(--font-size-lg);margin-top:2px">' + icon + '</span>' +
        '<div style="flex:1;min-width:0">' +
        '<div style="font-size:var(--font-size-sm);color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + escapeHtml(evt.description || evt.message || '') + '</div>' +
        '<div style="font-size:var(--font-size-xs);color:var(--text-muted)">' + fmtTimeAgo(evt.timestamp || evt.created_at) + '</div>' +
        '</div>' +
        '</div>';
    });
    return html + '</div>';
  }

  function renderNetworkStatusItem(label, enabled) {
    var cls = enabled ? 'badge-active' : 'badge-ended';
    var text = enabled ? 'Active' : 'Inactive';
    return '<div style="display:flex;align-items:center;justify-content:space-between;padding:var(--space-sm) var(--space-md);background:var(--bg-card);border:1px solid var(--border-subtle);border-radius:var(--radius-md)">' +
      '<span style="font-size:var(--font-size-sm);color:var(--text-secondary)">' + label + '</span>' +
      '<span class="badge ' + cls + '">' + text + '</span>' +
      '</div>';
  }

  function generateMockChartData() {
    var labels = [];
    var values = [];
    var now = new Date();
    for (var i = 6; i >= 0; i--) {
      var d = new Date(now);
      d.setDate(d.getDate() - i);
      labels.push(fmtDateShort(d));
      values.push(Math.floor(Math.random() * 500) + 100);
    }
    return { labels: labels, values: values };
  }

  function renderMiniChart(chartData) {
    var canvas = document.getElementById('overview-mini-chart');
    if (!canvas || typeof Chart === 'undefined') return;

    var ctx = canvas.getContext('2d');
    var gradient = ctx.createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, 'rgba(57, 165, 150, 0.3)');
    gradient.addColorStop(1, 'rgba(57, 165, 150, 0.01)');

    DB.charts.mini = new Chart(ctx, {
      type: 'line',
      data: {
        labels: chartData.labels || [],
        datasets: [{
          data: chartData.values || [],
          borderColor: DB.brand_color,
          backgroundColor: gradient,
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHoverBackgroundColor: DB.brand_color
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
        scales: {
          x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#555', font: { size: 10 } } },
          y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#555', font: { size: 10 } }, beginAtZero: true }
        }
      }
    });
  }

  // ============================================
  // CAMPAIGNS
  // ============================================
  function loadCampaigns() {
    $content.innerHTML = skeletonTable(5);

    dbFetch('/api/sponsored/campaigns?brand_id=' + encodeURIComponent(DB.brand_id))
      .then(function (data) {
        var campaigns = data.campaigns || data || [];
        DB.campaigns = Array.isArray(campaigns) ? campaigns : [];
        renderCampaignsView();
      })
      .catch(function (err) {
        console.error('Campaigns load error:', err);
        DB.campaigns = [];
        renderCampaignsView();
        showToast('Failed to load campaigns', 'error');
      });
  }

  function renderCampaignsView() {
    var html = '';

    html += '<div class="section-header">' +
      '<div><h2 class="section-title">Campaigns</h2><p class="section-subtitle">Manage your sponsored product campaigns</p></div>' +
      '<button class="btn btn-primary" id="btn-create-campaign">+ New Campaign</button>' +
      '</div>';

    if (DB.campaigns.length === 0) {
      html += emptyState('\uD83C\uDFAF', 'No campaigns yet', 'Create your first campaign to start promoting products across the network.',
        '<button class="btn btn-primary" id="btn-create-campaign-empty">Create Campaign</button>');
      $content.innerHTML = html;
      bindCampaignButtons();
      return;
    }

    html += '<div class="panel" style="padding:0;overflow:hidden">' +
      '<div class="table-wrapper"><table class="data-table"><thead><tr>' +
      '<th>Name</th><th>Status</th><th>Objective</th><th>Budget Spent</th>' +
      '<th>Impressions</th><th>Clicks</th><th>CTR</th><th>Conversions</th><th>CPA</th><th>Actions</th>' +
      '</tr></thead><tbody>';

    DB.campaigns.forEach(function (c) {
      var status = (c.status || 'active').toLowerCase();
      var statusClass = status === 'active' ? 'badge-active' : status === 'paused' ? 'badge-paused' : 'badge-ended';
      var obj = c.objective || 'product_views';
      var objLabel = obj.replace(/_/g, ' ').replace(/\b\w/g, function (l) { return l.toUpperCase(); });
      var budget = c.budget_spent || c.budgetSpent || 0;
      var totalBudget = c.budget || 1;
      var impressions = c.impressions || 0;
      var clicks = c.clicks || 0;
      var ctr = impressions > 0 ? ((clicks / impressions) * 100).toFixed(1) : '0.0';
      var conversions = c.conversions || 0;
      var cpa = conversions > 0 ? fmtPriceDec(budget / conversions) : '-';

      html += '<tr>' +
        '<td style="font-weight:var(--font-weight-medium)">' + escapeHtml(c.name || c.campaign_name || '-') + '</td>' +
        '<td><span class="badge ' + statusClass + '">' + status.charAt(0).toUpperCase() + status.slice(1) + '</span></td>' +
        '<td><span class="badge-pill">' + objLabel + '</span></td>' +
        '<td class="table-cell-mono">' + fmtPriceDec(budget) + '<div class="progress-bar mt-sm" style="width:80px"><div class="progress-fill' + (budget / totalBudget > 0.8 ? ' warning' : '') + '" style="width:' + Math.min(100, (budget / totalBudget) * 100) + '%"></div></div></td>' +
        '<td class="table-cell-mono">' + fmtNum(impressions) + '</td>' +
        '<td class="table-cell-mono">' + fmtNum(clicks) + '</td>' +
        '<td class="table-cell-mono">' + ctr + '%</td>' +
        '<td class="table-cell-mono">' + fmtNum(conversions) + '</td>' +
        '<td class="table-cell-mono">' + cpa + '</td>' +
        '<td><div class="table-cell-actions">' +
        '<button class="table-action-btn edit" data-edit="' + (c.id || c.campaign_id || '') + '">Edit</button>' +
        (status === 'active'
          ? '<button class="table-action-btn" data-pause="' + (c.id || c.campaign_id || '') + '">Pause</button>'
          : status === 'paused'
            ? '<button class="table-action-btn" data-resume="' + (c.id || c.campaign_id || '') + '">Resume</button>'
            : '') +
        '<button class="table-action-btn delete" data-delete="' + (c.id || c.campaign_id || '') + '">Delete</button>' +
        '</div></td>' +
        '</tr>';
    });

    html += '</tbody></table></div></div>';

    $content.innerHTML = html;
    bindCampaignButtons();
  }

  function bindCampaignButtons() {
    var createBtn = document.getElementById('btn-create-campaign') || document.getElementById('btn-create-campaign-empty');
    if (createBtn) {
      createBtn.addEventListener('click', function () { openCreateCampaign(); });
    }

    document.querySelectorAll('[data-edit]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var id = this.getAttribute('data-edit');
        var campaign = DB.campaigns.find(function (c) { return String(c.id || c.campaign_id) === String(id); });
        if (campaign) openEditCampaign(campaign);
      });
    });

    document.querySelectorAll('[data-pause]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        toggleCampaign(this.getAttribute('data-pause'), 'pause');
      });
    });

    document.querySelectorAll('[data-resume]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        toggleCampaign(this.getAttribute('data-resume'), 'resume');
      });
    });

    document.querySelectorAll('[data-delete]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        deleteCampaign(this.getAttribute('data-delete'));
      });
    });
  }

  function openCreateCampaign() {
    openCampaignModal(null);
  }

  function openEditCampaign(campaign) {
    openCampaignModal(campaign);
  }

  function openCampaignModal(existing) {
    var isEdit = !!existing;
    var title = isEdit ? 'Edit Campaign' : 'Create Campaign';
    var obj = (existing && existing.objective) || 'product_views';
    var name = (existing && (existing.name || existing.campaign_name)) || '';
    var budget = (existing && existing.budget) || '';
    var bidType = (existing && existing.bid_type) || 'CPC';
    var bidAmt = (existing && existing.bid_amount) || '';
    var startDate = toDateInputValue(existing && existing.start_date);
    var endDate = toDateInputValue(existing && existing.end_date);
    var cats = (existing && existing.target_categories) || [];
    var occasions = (existing && existing.target_occasions) || [];
    var styles = (existing && existing.target_styles) || [];
    var products = (existing && existing.products) || [];

    var objectives = [
      { value: 'product_views', label: 'Product Views' },
      { value: 'vton_interactions', label: 'VTON Interactions' },
      { value: 'clicks', label: 'Clicks' },
      { value: 'add_to_cart', label: 'Add to Cart' },
      { value: 'purchases', label: 'Purchases' },
      { value: 'revenue', label: 'Revenue' }
    ];

    var allCategories = ['Western Wear', 'Ethnic Wear', 'Activewear', 'Accessories', 'Footwear', 'Loungewear'];
    var allOccasions = ['Casual', 'Formal', 'Party', 'Wedding', 'Festival', 'Work', 'Travel'];
    var allStyles = ['Bohemian', 'Minimalist', 'Classic', 'Streetwear', 'Elegant', 'Sporty'];

    var html = '<div class="modal-overlay open" id="campaign-modal">' +
      '<div class="modal" style="max-width:620px">' +
      '<div class="modal-header"><h3 class="modal-title">' + title + '</h3><button class="modal-close" id="modal-close-btn">&times;</button></div>' +
      '<div class="modal-body">';

    // Campaign name
    html += '<div class="form-group">' +
      '<label class="form-label">Campaign Name <span class="required">*</span></label>' +
      '<input class="form-input" id="c-name" type="text" placeholder="e.g. Summer Collection Push" value="' + escapeHtml(name) + '">' +
      '</div>';

    // Objective
    html += '<div class="form-group"><label class="form-label">Objective <span class="required">*</span></label>' +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-xs)">';
    objectives.forEach(function (o) {
      var checked = o.value === obj ? ' checked' : '';
      html += '<div class="form-checkbox-group">' +
        '<input type="radio" name="c-obj" class="form-checkbox" value="' + o.value + '"' + checked + ' id="obj-' + o.value + '">' +
        '<label class="form-checkbox-label" for="obj-' + o.value + '">' + o.label + '</label>' +
        '</div>';
    });
    html += '</div></div>';

    // Products multi-select
    html += '<div class="form-group"><label class="form-label">Products</label>' +
      '<select class="form-select" id="c-products" multiple style="height:100px">';
    DB.products.forEach(function (p) {
      var selected = products.indexOf(p.id) > -1 || products.indexOf(String(p.id)) > -1 ? ' selected' : '';
      html += '<option value="' + (p.id || p.product_id || '') + '"' + selected + '>' + escapeHtml(p.title || p.name || 'Product') + '</option>';
    });
    html += '</select><p class="form-hint">Hold Ctrl/Cmd to select multiple</p></div>';

    // Target categories
    html += '<div class="form-group"><label class="form-label">Target Categories</label><div style="display:flex;flex-wrap:wrap;gap:var(--space-xs)">';
    allCategories.forEach(function (c) {
      var checked = cats.indexOf(c) > -1 ? ' checked' : '';
      html += '<div class="form-checkbox-group"><input type="checkbox" class="form-checkbox" value="' + c + '"' + checked + ' id="cat-' + c.replace(/\s/g, '-') + '"><label class="form-checkbox-label" for="cat-' + c.replace(/\s/g, '-') + '">' + c + '</label></div>';
    });
    html += '</div></div>';

    // Target occasions
    html += '<div class="form-group"><label class="form-label">Target Occasions</label><div style="display:flex;flex-wrap:wrap;gap:var(--space-xs)">';
    allOccasions.forEach(function (o) {
      var checked = occasions.indexOf(o) > -1 ? ' checked' : '';
      html += '<div class="form-checkbox-group"><input type="checkbox" class="form-checkbox" value="' + o + '"' + checked + ' id="occ-' + o + '"><label class="form-checkbox-label" for="occ-' + o + '">' + o + '</label></div>';
    });
    html += '</div></div>';

    // Target styles
    html += '<div class="form-group"><label class="form-label">Target Styles</label><div style="display:flex;flex-wrap:wrap;gap:var(--space-xs)">';
    allStyles.forEach(function (s) {
      var checked = styles.indexOf(s) > -1 ? ' checked' : '';
      html += '<div class="form-checkbox-group"><input type="checkbox" class="form-checkbox" value="' + s + '"' + checked + ' id="sty-' + s + '"><label class="form-checkbox-label" for="sty-' + s + '">' + s + '</label></div>';
    });
    html += '</div></div>';

    // Budget + Bid
    html += '<div class="form-row">' +
      '<div class="form-group"><label class="form-label">Budget (\u20B9 INR) <span class="required">*</span></label><input class="form-input" id="c-budget" type="number" min="100" step="100" placeholder="5000" value="' + budget + '"></div>' +
      '<div class="form-group"><label class="form-label">Bid Type</label>' +
      '<select class="form-select" id="c-bid-type"><option value="CPC"' + (bidType === 'CPC' ? ' selected' : '') + '>CPC (Cost per Click)</option><option value="CPA"' + (bidType === 'CPA' ? ' selected' : '') + '>CPA (Cost per Action)</option></select></div>' +
      '</div>';

    html += '<div class="form-group"><label class="form-label">Bid Amount (\u20B9)</label><input class="form-input" id="c-bid" type="number" min="1" step="0.5" placeholder="10" value="' + bidAmt + '"></div>';

    // Duration
    html += '<div class="form-row">' +
      '<div class="form-group"><label class="form-label">Start Date</label><input class="form-input" id="c-start" type="date" value="' + startDate + '"></div>' +
      '<div class="form-group"><label class="form-label">End Date</label><input class="form-input" id="c-end" type="date" value="' + endDate + '"></div>' +
      '</div>';

    html += '</div>'; // modal-body

    // Footer
    html += '<div class="modal-footer">' +
      '<button class="btn btn-ghost" id="modal-cancel-btn">Cancel</button>' +
      '<button class="btn btn-primary" id="modal-save-btn">' + (isEdit ? 'Update Campaign' : 'Create Campaign') + '</button>' +
      '</div></div></div>';

    document.body.insertAdjacentHTML('beforeend', html);

    var modal = document.getElementById('campaign-modal');
    var closeModal = function () { modal.remove(); };

    document.getElementById('modal-close-btn').addEventListener('click', closeModal);
    document.getElementById('modal-cancel-btn').addEventListener('click', closeModal);
    modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });

    document.getElementById('modal-save-btn').addEventListener('click', function () {
      var data = gatherCampaignForm(isEdit ? existing.id || existing.campaign_id : null);
      if (!data) return;
      saveCampaign(data, closeModal);
    });
  }

  function gatherCampaignForm(id) {
    var name = document.getElementById('c-name').value.trim();
    var obj = document.querySelector('input[name="c-obj"]:checked');
    var budget = document.getElementById('c-budget').value;
    var bidType = document.getElementById('c-bid-type').value;
    var bidAmt = document.getElementById('c-bid').value;
    var startDate = document.getElementById('c-start').value;
    var endDate = document.getElementById('c-end').value;

    if (!name) { showToast('Please enter a campaign name', 'error'); return null; }
    if (!obj) { showToast('Please select an objective', 'error'); return null; }
    if (!budget || Number(budget) < 100) { showToast('Budget must be at least \u20B9100', 'error'); return null; }

    var productSelect = document.getElementById('c-products');
    var selectedProducts = [];
    if (productSelect) {
      Array.from(productSelect.selectedOptions).forEach(function (opt) {
        selectedProducts.push(opt.value);
      });
    }

    var categories = [];
    document.querySelectorAll('#campaign-modal [id^="cat-"]:checked').forEach(function (el) { categories.push(el.value); });
    var occasions = [];
    document.querySelectorAll('#campaign-modal [id^="occ-"]:checked').forEach(function (el) { occasions.push(el.value); });
    var styles = [];
    document.querySelectorAll('#campaign-modal [id^="sty-"]:checked').forEach(function (el) { styles.push(el.value); });

    return {
      id: id || undefined,
      brand_id: DB.brand_id,
      name: name,
      objective: obj.value,
      products: selectedProducts,
      target_categories: categories,
      target_occasions: occasions,
      target_styles: styles,
      budget: Number(budget),
      bid_type: bidType,
      bid_amount: bidAmt ? Number(bidAmt) : null,
      start_date: startDate || null,
      end_date: endDate || null
    };
  }

  function saveCampaign(data, closeModal) {
    var method = data.id ? 'PUT' : 'POST';
    var path = data.id ? '/api/sponsored/campaigns/' + data.id : '/api/sponsored/campaigns';

    dbFetch(path, { method: method, body: data })
      .then(function () {
        showToast(data.id ? 'Campaign updated' : 'Campaign created', 'success');
        if (closeModal) closeModal();
        loadCampaigns();
      })
      .catch(function (err) {
        console.error('Save campaign error:', err);
        showToast('Failed to save campaign', 'error');
      });
  }

  function toggleCampaign(id, action) {
    dbFetch('/api/sponsored/campaigns/' + id + '/' + action, { method: 'PUT' })
      .then(function () {
        showToast('Campaign ' + (action === 'pause' ? 'paused' : 'resumed'), 'success');
        loadCampaigns();
      })
      .catch(function (err) {
        console.error('Toggle campaign error:', err);
        showToast('Failed to update campaign', 'error');
      });
  }

  function deleteCampaign(id) {
    showConfirm('Are you sure you want to delete this campaign? This action cannot be undone.').then(function (ok) {
      if (!ok) return;
      dbFetch('/api/sponsored/campaigns/' + id, { method: 'DELETE' })
        .then(function () {
          showToast('Campaign deleted', 'success');
          loadCampaigns();
        })
        .catch(function (err) {
          console.error('Delete campaign error:', err);
          showToast('Failed to delete campaign', 'error');
        });
    });
  }

  // ============================================
  // PRODUCTS
  // ============================================
  function loadProducts() {
    $content.innerHTML = '<div class="product-grid" style="grid-template-columns:repeat(auto-fill,minmax(260px,1fr))">' +
      '<div class="product-card"><div class="skeleton skeleton-card" style="height:160px"></div><div style="padding:var(--space-md)"><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text" style="width:50%"></div></div></div>'.repeat(6) +
      '</div>';

    dbFetch('/api/network/product/' + encodeURIComponent(DB.brand_id))
      .then(function (data) {
        var products = data.products || data || [];
        DB.products = Array.isArray(products) ? products : [];
        renderProductsView();
      })
      .catch(function (err) {
        console.error('Products load error:', err);
        DB.products = [];
        renderProductsView();
        showToast('Failed to load products', 'error');
      });
  }

  function renderProductsView() {
    var html = '';

    html += '<div class="section-header">' +
      '<div><h2 class="section-title">Product Catalog</h2><p class="section-subtitle">Manage products available in the Narrative Ad Network</p></div>' +
      '<div style="display:flex;gap:var(--space-sm)">' +
      '<label class="btn btn-secondary" style="cursor:pointer"><input type="file" id="csv-upload" accept=".csv" style="display:none">Upload CSV</label>' +
      '<button class="btn btn-primary" id="btn-toggle-all">Toggle All Eligibility</button>' +
      '</div>' +
      '</div>';

    // Filters
    html += '<div class="panel" style="padding:var(--space-md);margin-bottom:var(--space-lg)">' +
      '<div style="display:flex;gap:var(--space-sm);flex-wrap:wrap;align-items:center">' +
      '<input class="form-input" id="product-search" type="text" placeholder="Search products..." style="width:260px">' +
      '<select class="form-select" id="product-filter-cat" style="width:180px"><option value="">All Categories</option></select>' +
      '<select class="form-select" id="product-filter-status" style="width:160px"><option value="">All Status</option><option value="eligible">Eligible</option><option value="ineligible">Ineligible</option></select>' +
      '</div></div>';

    if (DB.products.length === 0) {
      html += emptyState('\uD83D\uDCE6', 'No products found', 'Upload your product catalog to get started with the Narrative Ad Network.');
      $content.innerHTML = html;
      bindProductButtons();
      return;
    }

    // Populate category filter
    var cats = {};
    DB.products.forEach(function (p) {
      var cat = p.category || p.product_type || '';
      if (cat) cats[cat] = true;
    });

    html += '<div class="product-grid" id="product-grid">';
    DB.products.forEach(function (p, idx) {
      var eligible = p.eligible !== false && p.eligible !== 0;
      var cat = p.category || p.product_type || '-';
      var price = p.price || 0;
      var img = p.image || p.image_url || p.featured_image || '';

      html += '<div class="product-card" data-idx="' + idx + '" style="animation-delay:' + (idx * 0.05) + 's">' +
        '<div class="product-card-image">' +
        (img ? '<img src="' + escapeHtml(img) + '" alt="' + escapeHtml(p.title || '') + '" loading="lazy">' : '\uD83D\uDC57') +
        '</div>' +
        '<div class="product-card-body">' +
        '<h4 class="product-card-title">' + escapeHtml(p.title || p.name || 'Product') + '</h4>' +
        '<div class="product-card-price">' + fmtPrice(price) + '</div>' +
        '<div class="product-card-meta">' +
        '<span class="product-card-status"><span class="badge-pill">' + escapeHtml(cat) + '</span></span>' +
        '<label class="product-card-toggle tooltip" data-tooltip="' + (eligible ? 'Eligible' : 'Not eligible') + '">' +
        '<input type="checkbox" data-toggle-eligible="' + (p.id || p.product_id || idx) + '"' + (eligible ? ' checked' : '') + '>' +
        '<span class="product-toggle-slider"></span>' +
        '</label>' +
        '</div></div></div>';
    });
    html += '</div>';

    $content.innerHTML = html;

    // Populate category options
    var catSelect = document.getElementById('product-filter-cat');
    Object.keys(cats).sort().forEach(function (c) {
      catSelect.insertAdjacentHTML('beforeend', '<option value="' + escapeHtml(c) + '">' + escapeHtml(c) + '</option>');
    });

    bindProductButtons();
  }

  function bindProductButtons() {
    var csvUpload = document.getElementById('csv-upload');
    if (csvUpload) {
      csvUpload.addEventListener('change', function () {
        if (this.files.length > 0) uploadProducts(this.files[0]);
      });
    }

    var toggleAll = document.getElementById('btn-toggle-all');
    if (toggleAll) {
      toggleAll.addEventListener('click', function () {
        var allChecked = DB.products.every(function (p) { return p.eligible !== false; });
        DB.products.forEach(function (p) {
          toggleProductEligibility(p.id || p.product_id, !allChecked);
        });
      });
    }

    document.querySelectorAll('[data-toggle-eligible]').forEach(function (el) {
      el.addEventListener('change', function () {
        var id = this.getAttribute('data-toggle-eligible');
        toggleProductEligibility(id, this.checked);
      });
    });

    var search = document.getElementById('product-search');
    var filterCat = document.getElementById('product-filter-cat');
    var filterStatus = document.getElementById('product-filter-status');

    function applyFilters() {
      var q = (search && search.value || '').toLowerCase();
      var cat = filterCat && filterCat.value || '';
      var status = filterStatus && filterStatus.value || '';

      document.querySelectorAll('.product-card[data-idx]').forEach(function (card) {
        var idx = parseInt(card.getAttribute('data-idx'), 10);
        var p = DB.products[idx];
        if (!p) return;

        var title = (p.title || p.name || '').toLowerCase();
        var pCat = p.category || p.product_type || '';
        var eligible = p.eligible !== false;

        var matchQ = !q || title.indexOf(q) > -1;
        var matchCat = !cat || pCat === cat;
        var matchStatus = !status || (status === 'eligible' ? eligible : !eligible);

        card.style.display = (matchQ && matchCat && matchStatus) ? '' : 'none';
      });
    }

    if (search) search.addEventListener('input', applyFilters);
    if (filterCat) filterCat.addEventListener('change', applyFilters);
    if (filterStatus) filterStatus.addEventListener('change', applyFilters);
  }

  function toggleProductEligibility(id, eligible) {
    var product = DB.products.find(function (p) { return String(p.id || p.product_id) === String(id); });
    if (product) {
      product.eligible = eligible;
    }

    dbFetch('/api/network/product/' + encodeURIComponent(DB.brand_id) + '/' + id, {
      method: 'PUT',
      body: { eligible: eligible }
    }).then(function () {
      showToast('Product eligibility updated', 'success');
    }).catch(function (err) {
      console.error('Toggle eligibility error:', err);
      if (product) product.eligible = !eligible;
      showToast('Failed to update product', 'error');
    });
  }

  function uploadProducts(file) {
    if (!file) return;

    showToast('Uploading products...', 'info');

    var reader = new FileReader();
    reader.onload = function (e) {
      var csv = e.target.result;

      dbFetch('/api/brand/catalogs', {
        method: 'POST',
        body: { brand_id: DB.brand_id, csv: csv, filename: file.name }
      }).then(function () {
        showToast('Products uploaded successfully', 'success');
        loadProducts();
      }).catch(function (err) {
        console.error('Upload error:', err);
        showToast('Failed to upload products', 'error');
      });
    };
    reader.readAsText(file);
  }

  // ============================================
  // NETWORK SETTINGS
  // ============================================
  function loadNetworkSettings() {
    $content.innerHTML = skeletonCardGrid(1) + skeletonCardGrid(1);

    dbFetch('/api/b2b_gateway?brand_id=' + encodeURIComponent(DB.brand_id))
      .then(function (data) {
        DB.network_settings = data.settings || data || {};
        renderNetworkSettingsView();
      })
      .catch(function (err) {
        console.error('Network settings load error:', err);
        DB.network_settings = {};
        renderNetworkSettingsView();
        showToast('Failed to load network settings', 'error');
      });
  }

  function renderNetworkSettingsView() {
    var s = DB.network_settings;

    var toggles = [
      {
        key: 'vton_enabled',
        label: 'VTON Enabled',
        desc: 'Let customers try your products with AI virtual try-on',
        default: false
      },
      {
        key: 'receive_recommendations',
        label: 'Receive Recommendations',
        desc: 'Show compatible products from partner brands on your site',
        default: false
      },
      {
        key: 'distribute_products',
        label: 'Distribute Products',
        desc: 'Allow your products to appear on partner brand websites',
        default: false
      },
      {
        key: 'promote_products',
        label: 'Promote Products',
        desc: 'Pay to increase exposure across the network',
        default: false
      }
    ];

    var html = '<div class="section-header">' +
      '<div><h2 class="section-title">Network Settings</h2><p class="section-subtitle">Configure how your brand participates in the Narrative Ad Network</p></div>' +
      '</div>';

    html += '<div class="panel"><div class="panel-header"><span class="panel-title">Participation Toggles</span></div>';
    html += '<div class="network-toggles">';

    toggles.forEach(function (t) {
      var val = s[t.key] !== undefined ? s[t.key] : t.default;
      html += '<div class="toggle-row' + (val ? ' active' : '') + '" id="toggle-row-' + t.key + '">' +
        '<div class="toggle-info">' +
        '<span class="toggle-label">' + t.label + '</span>' +
        '<span class="toggle-description">' + t.desc + '</span>' +
        '</div>' +
        '<label class="toggle-switch">' +
        '<input type="checkbox" data-setting="' + t.key + '"' + (val ? ' checked' : '') + '>' +
        '<span class="toggle-slider"></span>' +
        '</label>' +
        '</div>';
    });

    html += '</div></div>';

    // Promotion settings (shown when promote is on)
    var promoteOn = s.promote_products || false;
    html += '<div class="panel" id="promotion-settings" style="' + (promoteOn ? '' : 'display:none') + '">' +
      '<div class="panel-header"><span class="panel-title">Promotion Settings</span></div>' +
      '<div class="form-row">' +
      '<div class="form-group"><label class="form-label">Monthly Promotion Budget (\u20B9 INR)</label><input class="form-input" id="promo-budget" type="number" min="500" step="500" placeholder="10000" value="' + (s.promo_budget || '') + '"></div>' +
      '<div class="form-group"><label class="form-label">Max CPC Bid (\u20B9)</label><input class="form-input" id="promo-cpc" type="number" min="1" step="0.5" placeholder="15" value="' + (s.max_cpc_bid || '') + '"></div>' +
      '</div>' +
      '<div class="form-group"><label class="form-label">Target Categories for Promotion</label>' +
      '<div style="display:flex;flex-wrap:wrap;gap:var(--space-xs)">' +
      ['Western Wear', 'Ethnic Wear', 'Activewear', 'Accessories', 'Footwear', 'Loungewear'].map(function (c) {
        var checked = (s.promo_categories || []).indexOf(c) > -1 ? ' checked' : '';
        return '<div class="form-checkbox-group"><input type="checkbox" class="form-checkbox" value="' + c + '"' + checked + ' id="promo-cat-' + c.replace(/\s/g, '-') + '"><label class="form-checkbox-label" for="promo-cat-' + c.replace(/\s/g, '-') + '">' + c + '</label></div>';
      }).join('') +
      '</div></div>' +
      '</div>';

    // Save
    html += '<div style="display:flex;justify-content:flex-end;margin-top:var(--space-lg)">' +
      '<button class="btn btn-primary btn-lg" id="btn-save-settings">Save Network Settings</button>' +
      '</div>';

    $content.innerHTML = html;

    // Bind toggle behavior
    document.querySelectorAll('[data-setting]').forEach(function (input) {
      input.addEventListener('change', function () {
        var row = this.closest('.toggle-row');
        if (row) row.classList.toggle('active', this.checked);

        if (this.getAttribute('data-setting') === 'promote_products') {
          var promoPanel = document.getElementById('promotion-settings');
          if (promoPanel) promoPanel.style.display = this.checked ? '' : 'none';
        }
      });
    });

    document.getElementById('btn-save-settings').addEventListener('click', saveNetworkSettings);
  }

  function saveNetworkSettings() {
    var settings = {};
    document.querySelectorAll('[data-setting]').forEach(function (input) {
      settings[input.getAttribute('data-setting')] = input.checked;
    });

    if (settings.promote_products) {
      settings.promo_budget = Number(document.getElementById('promo-budget').value) || 0;
      settings.max_cpc_bid = Number(document.getElementById('promo-cpc').value) || 0;
      settings.promo_categories = [];
      document.querySelectorAll('[id^="promo-cat-"]:checked').forEach(function (el) {
        settings.promo_categories.push(el.value);
      });
    }

    dbFetch('/api/b2b_gateway', {
      method: 'POST',
      body: { brand_id: DB.brand_id, settings: settings }
    }).then(function () {
      DB.network_settings = settings;
      showToast('Network settings saved', 'success');
    }).catch(function (err) {
      console.error('Save settings error:', err);
      showToast('Failed to save settings', 'error');
    });
  }

  // ============================================
  // ANALYTICS
  // ============================================
  function loadAnalytics(range) {
    DB.dateRange = range || '7d';
    $content.innerHTML = '<div class="skeleton skeleton-card" style="height:120px"></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-lg)"><div class="skeleton skeleton-card" style="height:320px"></div><div class="skeleton skeleton-card" style="height:320px"></div></div>';

    dbFetch('/api/network/report?brand_id=' + encodeURIComponent(DB.brand_id) + '&range=' + DB.dateRange)
      .then(function (data) {
        DB.analytics = data;
        renderAnalyticsView(data);
      })
      .catch(function (err) {
        console.error('Analytics load error:', err);
        renderAnalyticsView({});
        showToast('Failed to load analytics', 'error');
      });
  }

  function renderAnalyticsView(data) {
    var html = '';

    // Date range picker
    html += '<div class="section-header">' +
      '<div><h2 class="section-title">Analytics</h2><p class="section-subtitle">Performance metrics for your brand on the network</p></div>' +
      '<div style="display:flex;align-items:center;gap:var(--space-sm)">' +
      '<div class="chart-filters">' +
      ['7d', '30d', '90d'].map(function (r) {
        return '<button class="chart-filter-btn' + (DB.dateRange === r ? ' active' : '') + '" data-range="' + r + '">' + r + '</button>';
      }).join('') +
      '<input class="form-input" type="date" id="analytics-custom-start" style="width:150px;display:none">' +
      '<input class="form-input" type="date" id="analytics-custom-end" style="width:150px;display:none">' +
      '</div>' +
      '<button class="btn btn-secondary btn-sm" id="btn-export-csv">Export CSV</button>' +
      '</div>' +
      '</div>';

    // Charts row
    html += '<div class="charts-grid">' +
      '<div class="chart-container"><div class="chart-header"><span class="chart-title">Performance Over Time</span></div><div style="height:300px"><canvas id="analytics-line-chart"></canvas></div></div>' +
      '<div class="chart-container"><div class="chart-header"><span class="chart-title">Revenue by Category</span></div><div style="height:300px"><canvas id="analytics-doughnut-chart"></canvas></div></div>' +
      '</div>';

    html += '<div class="chart-container"><div class="chart-header"><span class="chart-title">Top Performing Products</span></div><div style="height:300px"><canvas id="analytics-bar-chart"></canvas></div></div>';

    // Metrics table
    var metrics = data.metrics || {};
    html += '<div class="panel"><div class="panel-header"><span class="panel-title">Key Metrics</span></div>' +
      '<div class="table-wrapper"><table class="data-table"><thead><tr><th>Metric</th><th>Value</th><th>Trend</th></tr></thead><tbody>' +
      renderMetricRow('Outfit Completion Rate', (metrics.outfit_completion_rate || 0).toFixed(1) + '%', metrics.outfit_completion_trend || 0) +
      renderMetricRow('Cross-brand Conversion', (metrics.cross_brand_conversion || 0).toFixed(1) + '%', metrics.cross_brand_trend || 0) +
      renderMetricRow('VTON Interaction Rate', (metrics.vton_interaction_rate || 0).toFixed(1) + '%', metrics.vton_trend || 0) +
      renderMetricRow('Avg Order Value', fmtPrice(metrics.avg_order_value || 0), metrics.aov_trend || 0) +
      '</tbody></table></div></div>';

    $content.innerHTML = html;

    renderAnalyticsCharts(data);

    // Bind range buttons
    document.querySelectorAll('[data-range]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        loadAnalytics(this.getAttribute('data-range'));
      });
    });

    var exportBtn = document.getElementById('btn-export-csv');
    if (exportBtn) {
      exportBtn.addEventListener('click', function () { exportAnalyticsCSV(data); });
    }
  }

  function renderMetricRow(name, value, trend) {
    var cls = trend >= 0 ? 'text-success' : 'text-danger';
    var arrow = trend >= 0 ? '\u2191' : '\u2193';
    return '<tr><td style="font-weight:var(--font-weight-medium)">' + name + '</td>' +
      '<td class="table-cell-mono">' + value + '</td>' +
      '<td class="table-cell-mono ' + cls + '">' + arrow + ' ' + Math.abs(trend).toFixed(1) + '%</td></tr>';
  }

  function renderAnalyticsCharts(data) {
    if (typeof Chart === 'undefined') return;

    var timeData = data.time_series || data.timeSeries || generateTimeSeriesData();
    var catData = data.revenue_by_category || data.revenueByCategory || generateCategoryData();
    var topProducts = data.top_products || data.topProducts || generateTopProductsData();

    // Line chart
    var lineCtx = document.getElementById('analytics-line-chart');
    if (lineCtx) {
      var gradient = lineCtx.getContext('2d').createLinearGradient(0, 0, 0, 280);
      gradient.addColorStop(0, 'rgba(57, 165, 150, 0.2)');
      gradient.addColorStop(1, 'rgba(57, 165, 150, 0.01)');

      DB.charts.line = new Chart(lineCtx, {
        type: 'line',
        data: {
          labels: timeData.labels || [],
          datasets: [
            {
              label: 'Impressions',
              data: timeData.impressions || [],
              borderColor: '#39A596',
              backgroundColor: gradient,
              borderWidth: 2,
              fill: true,
              tension: 0.4,
              pointRadius: 2,
              pointHoverRadius: 5
            },
            {
              label: 'Clicks',
              data: timeData.clicks || [],
              borderColor: '#818CF8',
              borderWidth: 2,
              tension: 0.4,
              pointRadius: 2,
              pointHoverRadius: 5,
              fill: false
            },
            {
              label: 'Conversions',
              data: timeData.conversions || [],
              borderColor: '#F59E0B',
              borderWidth: 2,
              tension: 0.4,
              pointRadius: 2,
              pointHoverRadius: 5,
              fill: false
            }
          ]
        },
        options: chartLineOptions()
      });
    }

    // Doughnut chart
    var doughnutCtx = document.getElementById('analytics-doughnut-chart');
    if (doughnutCtx) {
      DB.charts.doughnut = new Chart(doughnutCtx, {
        type: 'doughnut',
        data: {
          labels: catData.labels || [],
          datasets: [{
            data: catData.values || [],
            backgroundColor: ['#39A596', '#818CF8', '#F59E0B', '#EF4444', '#D4A843', '#34D399'],
            borderWidth: 0,
            spacing: 2
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '65%',
          plugins: {
            legend: {
              position: 'right',
              labels: { color: '#8a8a9a', font: { size: 11 }, padding: 12, usePointStyle: true, pointStyleWidth: 8 }
            },
            tooltip: {
              callbacks: {
                label: function (context) {
                  return context.label + ': ' + fmtPriceDec(context.raw);
                }
              }
            }
          }
        }
      });
    }

    // Bar chart
    var barCtx = document.getElementById('analytics-bar-chart');
    if (barCtx) {
      DB.charts.bar = new Chart(barCtx, {
        type: 'bar',
        data: {
          labels: topProducts.labels || [],
          datasets: [{
            label: 'Revenue',
            data: topProducts.values || [],
            backgroundColor: 'rgba(57, 165, 150, 0.6)',
            borderColor: '#39A596',
            borderWidth: 1,
            borderRadius: 6,
            maxBarThickness: 50
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: 'y',
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#555', font: { size: 10 }, callback: function (v) { return fmtPrice(v); } } },
            y: { grid: { display: false }, ticks: { color: '#8a8a9a', font: { size: 11 } } }
          }
        }
      });
    }
  }

  function chartLineOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: '#8a8a9a', font: { size: 11 }, usePointStyle: true, pointStyleWidth: 8, padding: 16 } },
        tooltip: { mode: 'index', intersect: false }
      },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#555', font: { size: 10 }, maxRotation: 0 } },
        y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#555', font: { size: 10 } }, beginAtZero: true }
      }
    };
  }

  function generateTimeSeriesData() {
    var labels = [];
    var impressions = [];
    var clicks = [];
    var conversions = [];
    var now = new Date();
    var days = DB.dateRange === '90d' ? 90 : DB.dateRange === '30d' ? 30 : 7;

    for (var i = days - 1; i >= 0; i--) {
      var d = new Date(now);
      d.setDate(d.getDate() - i);
      labels.push(fmtDateShort(d));
      impressions.push(Math.floor(Math.random() * 2000) + 500);
      clicks.push(Math.floor(Math.random() * 200) + 30);
      conversions.push(Math.floor(Math.random() * 30) + 2);
    }
    return { labels: labels, impressions: impressions, clicks: clicks, conversions: conversions };
  }

  function generateCategoryData() {
    return {
      labels: ['Western Wear', 'Ethnic Wear', 'Accessories', 'Footwear', 'Activewear'],
      values: [45000, 32000, 18000, 12000, 8000]
    };
  }

  function generateTopProductsData() {
    return {
      labels: ['Silk Anarkali', 'Linen Blazer', 'Embroidered Kurti', 'Canvas Sneakers', 'Cotton Palazzo'],
      values: [32000, 28000, 21000, 15000, 12000]
    };
  }

  function exportAnalyticsCSV(data) {
    var rows = [['Date', 'Impressions', 'Clicks', 'Conversions', 'Revenue']];
    var timeData = data.time_series || data.timeSeries || generateTimeSeriesData();

    for (var i = 0; i < (timeData.labels || []).length; i++) {
      rows.push([
        timeData.labels[i],
        timeData.impressions[i] || 0,
        timeData.clicks[i] || 0,
        timeData.conversions[i] || 0,
        ''
      ]);
    }

    var csv = rows.map(function (r) { return r.join(','); }).join('\n');
    var blob = new Blob([csv], { type: 'text/csv' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'narrative-analytics-' + DB.dateRange + '.csv';
    a.click();
    URL.revokeObjectURL(url);

    showToast('CSV exported successfully', 'success');
  }

  // ============================================
  // WALLET / BILLING
  // ============================================
  function loadWallet() {
    $content.innerHTML = skeletonCardGrid(1) + skeletonTable(5);

    dbFetch('/api/wallet?brand_id=' + encodeURIComponent(DB.brand_id))
      .then(function (data) {
        DB.wallet = {
          balance: data.balance || 0,
          transactions: data.transactions || data.history || [],
          invoices: data.invoices || []
        };
        renderWalletView();
      })
      .catch(function (err) {
        console.error('Wallet load error:', err);
        DB.wallet = { balance: 0, transactions: [], invoices: [] };
        renderWalletView();
        showToast('Failed to load wallet data', 'error');
      });
  }

  function renderWalletView() {
    var w = DB.wallet;

    var html = '<div class="section-header">' +
      '<div><h2 class="section-title">Billing & Wallet</h2><p class="section-subtitle">Manage your account balance and view transaction history</p></div>' +
      '</div>';

    // Balance card
    html += '<div class="wallet-section">' +
      '<div class="wallet-card">' +
      '<div class="wallet-balance-label">Available Balance</div>' +
      '<div class="wallet-balance-amount"><span class="currency">\u20B9</span>' + fmtNum(w.balance) + '</div>' +
      '<div class="wallet-actions">' +
      '<button class="btn btn-primary btn-lg" id="btn-topup">\u2B50 Top Up Wallet</button>' +
      '<button class="btn btn-secondary" id="btn-add-funds">Add Funds via Razorpay</button>' +
      '</div>' +
      '</div>';

    // Quick amounts
    html += '<div style="display:flex;gap:var(--space-sm);margin-bottom:var(--space-lg);flex-wrap:wrap">';
    [500, 1000, 2500, 5000, 10000].forEach(function (amt) {
      html += '<button class="btn btn-secondary btn-sm quick-topup" data-amount="' + amt + '">' + fmtPrice(amt) + '</button>';
    });
    html += '</div></div>';

    // Transaction history
    html += '<div class="panel">' +
      '<div class="panel-header"><span class="panel-title">Transaction History</span></div>';

    if (w.transactions.length === 0) {
      html += emptyState('\uD83D\uDCB3', 'No transactions yet', 'Your transaction history will appear here once you start using the network.');
    } else {
      html += '<div class="transaction-list">';
      w.transactions.forEach(function (t) {
        var isCredit = t.type === 'credit' || t.amount > 0;
        var icon = isCredit ? '\u2B06' : '\u2B07';
        var iconClass = isCredit ? 'credit' : 'debit';
        var amtClass = isCredit ? 'credit' : 'debit';
        var amtPrefix = isCredit ? '+' : '-';

        html += '<div class="transaction-item">' +
          '<div class="transaction-icon ' + iconClass + '">' + icon + '</div>' +
          '<div class="transaction-details">' +
          '<div class="transaction-title">' + escapeHtml(t.description || t.title || t.narration || '-') + '</div>' +
          '<div class="transaction-date">' + fmtDate(t.date || t.created_at || t.timestamp) + '</div>' +
          '</div>' +
          '<div class="transaction-amount ' + amtClass + '">' + amtPrefix + fmtPriceDec(Math.abs(t.amount || 0)) + '</div>' +
          '</div>';
      });
      html += '</div>';
    }
    html += '</div>';

    // Invoices
    if (w.invoices && w.invoices.length > 0) {
      html += '<div class="panel"><div class="panel-header"><span class="panel-title">Invoices</span></div>';
      html += '<div class="table-wrapper"><table class="data-table"><thead><tr><th>Invoice #</th><th>Date</th><th>Amount</th><th>Status</th><th>Action</th></tr></thead><tbody>';
      w.invoices.forEach(function (inv) {
        var statusCls = inv.status === 'paid' ? 'badge-success' : inv.status === 'pending' ? 'badge-paused' : 'badge-danger';
        html += '<tr>' +
          '<td class="table-cell-mono">' + escapeHtml(inv.invoice_number || inv.id || '-') + '</td>' +
          '<td>' + fmtDate(inv.date || inv.created_at) + '</td>' +
          '<td class="table-cell-mono">' + fmtPriceDec(inv.amount || 0) + '</td>' +
          '<td><span class="badge ' + statusCls + '">' + (inv.status || '-') + '</span></td>' +
          '<td>' + (inv.download_url || inv.pdf_url ? '<a href="' + (inv.download_url || inv.pdf_url) + '" class="btn btn-ghost btn-sm" target="_blank">Download</a>' : '-') + '</td>' +
          '</tr>';
      });
      html += '</tbody></table></div></div>';
    }

    $content.innerHTML = html;
    bindWalletButtons();
  }

  function bindWalletButtons() {
    document.querySelectorAll('.quick-topup').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var amt = parseInt(this.getAttribute('data-amount'), 10);
        topUpWallet(amt);
      });
    });

    var topupBtn = document.getElementById('btn-topup');
    if (topupBtn) {
      topupBtn.addEventListener('click', function () {
        openTopUpModal();
      });
    }

    var addFundsBtn = document.getElementById('btn-add-funds');
    if (addFundsBtn) {
      addFundsBtn.addEventListener('click', function () {
        openTopUpModal();
      });
    }
  }

  function openTopUpModal() {
    var html = '<div class="modal-overlay open" id="topup-modal">' +
      '<div class="modal" style="max-width:400px">' +
      '<div class="modal-header"><h3 class="modal-title">Top Up Wallet</h3><button class="modal-close" id="topup-close">&times;</button></div>' +
      '<div class="modal-body">' +
      '<div class="form-group"><label class="form-label">Amount (\u20B9 INR)</label><input class="form-input" id="topup-amount" type="number" min="100" step="100" placeholder="1000"></div>' +
      '<p class="form-hint">Minimum top-up amount: \u20B9100</p>' +
      '</div>' +
      '<div class="modal-footer">' +
      '<button class="btn btn-ghost" id="topup-cancel">Cancel</button>' +
      '<button class="btn btn-primary" id="topup-confirm">Pay via Razorpay</button>' +
      '</div></div></div>';

    document.body.insertAdjacentHTML('beforeend', html);

    var modal = document.getElementById('topup-modal');
    var close = function () { modal.remove(); };

    document.getElementById('topup-close').addEventListener('click', close);
    document.getElementById('topup-cancel').addEventListener('click', close);
    modal.addEventListener('click', function (e) { if (e.target === modal) close(); });

    document.getElementById('topup-confirm').addEventListener('click', function () {
      var amt = parseInt(document.getElementById('topup-amount').value, 10);
      if (!amt || amt < 100) {
        showToast('Minimum amount is \u20B9100', 'error');
        return;
      }
      close();
      topUpWallet(amt);
    });
  }

  function topUpWallet(amount) {
    if (!amount || amount < 100) {
      showToast('Minimum top-up is \u20B9100', 'error');
      return;
    }

    showToast('Processing payment of ' + fmtPrice(amount) + '...', 'info');

    dbFetch('/api/wallet/topup', {
      method: 'POST',
      body: { brand_id: DB.brand_id, amount: amount }
    }).then(function (res) {
      if (res.payment_url || res.razorpay_url) {
        window.location.href = res.payment_url || res.razorpay_url;
        return;
      }

      DB.wallet.balance = (DB.wallet.balance || 0) + amount;
      DB.wallet.transactions.unshift({
        type: 'credit',
        amount: amount,
        description: 'Wallet top-up',
        date: new Date().toISOString(),
        created_at: new Date().toISOString()
      });

      showToast('Successfully added ' + fmtPrice(amount) + ' to wallet', 'success');
      renderWalletView();
    }).catch(function (err) {
      console.error('Top-up error:', err);
      showToast('Payment failed. Please try again.', 'error');
    });
  }

  // ============================================
  // Boot
  // ============================================
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
