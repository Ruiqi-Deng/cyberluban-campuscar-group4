Page({
  data: {
    role: '校内',
    sample: '骨髓样本',
    temp: '4°C',
    senderId: 'S2024001',
    sampleCode: '',
    pickupCode: '',
    robotStatus: '加载中...',
    taskList: [],
    createResult: '',
    pickupResult: '',
    origin: '实验室',
    target: '校门口',
    createdSampleCode: '',
    createdPickupCode: '',
    isSubmitting: false
  },

  onLoad(options) {
    const mode = options.mode || 'send';
    const title = mode === 'send' ? '📤 寄件' : '📥 取件';
    this.setData({ mode, pageTitle: title });
    const role = options.role || '校内';
    this.setData({ role: role });
    if (role === '校内') this.setData({ senderId: 'S2024001' });
    else this.setData({ senderId: '13800138000' });
    
    this.refresh();
    this.refreshTimer = setInterval(() => this.refresh(), 5000);
  },

  onUnload() {
    if (this.refreshTimer) clearInterval(this.refreshTimer);
  },

  getBaseUrl() {
    return getApp().globalData.apiBase;
  },

  getErrorMessage(res, fallback) {
    if (res && res.data) {
      if (typeof res.data.detail === 'string') return res.data.detail;
      if (typeof res.data.message === 'string') return res.data.message;
    }
    return fallback;
  },

  refresh() {
    const base = this.getBaseUrl();
    console.log('当前请求的Base地址:', base);
    wx.request({
      url: `${base}/api/robot/status`,
      success: (res) => {
        if (res.statusCode === 200 && res.data) {
          const latestTask = res.data.latest_task;
          this.setData({
            robotStatus: latestTask ? latestTask.status_message : '🟢 暂无任务，等待寄件'
          });
        }
      },
      fail: () => this.setData({ robotStatus: '⚠️ 无法连接后端' })
    });
    wx.request({
      url: `${base}/tasks`,
      success: (res) => {
        if (Array.isArray(res.data)) this.setData({ taskList: res.data });
      }
    });
  },

  createTask() {
    const sample = this.data.sample.trim();
    const temp = this.data.temp.trim();
    const origin = this.data.origin.trim();
    const target = this.data.target.trim();
    if (!sample || !temp || !origin || !target) {
      this.setData({ createResult: '❌ 请完整填写起点、终点、样品名称和温湿度要求' });
      return;
    }
    const base = this.getBaseUrl();
    this.setData({ isSubmitting: true, createResult: '正在创建寄件任务…' });
    wx.request({
      url: `${base}/api/tasks`,
      method: 'POST',
      header: { 'Content-Type': 'application/json' },
      data: {
        sample_name: sample,
        temp_humidity: temp,
        sender_id: this.data.senderId,
        // 当前底盘尚未接入导航，先传 0；接入地点坐标表后替换。
        origin: { name: origin, latitude: 0, longitude: 0 },
        target: { name: target, latitude: 0, longitude: 0 }
      },
      success: (res) => {
        if (res.statusCode === 200 && res.data.sample_code) {
          const sampleCode = String(res.data.sample_code);
          const pickupCode = String(res.data.pickup_code).padStart(4, '0');
          wx.showModal({
            title: '📦 寄件成功',
            content: `样品编码：${sampleCode}\n取件码：${pickupCode}\n\n请将这两个编码告知取件人。`,
            showCancel: false,
            confirmText: '我知道了'
          });
          this.setData({
            createdSampleCode: sampleCode,
            createdPickupCode: pickupCode,
            createResult: '✅ 寄件成功，NUC 将自动接收任务'
          });
          this.refresh();
        } else {
          this.setData({ createResult: `❌ ${this.getErrorMessage(res, '创建失败')}` });
        }
      },
      fail: () => {
        this.setData({ createResult: '❌ 无法连接云端，请检查 API 地址和域名校验设置' });
      },
      complete: () => this.setData({ isSubmitting: false })
    });
  },

  pickupTask() {
    const sampleCode = this.data.sampleCode.trim();
    const pickupCode = this.data.pickupCode.trim();
    if (!sampleCode || !/^\d{4}$/.test(pickupCode)) {
      this.setData({ pickupResult: '❌ 请输入样品编码和4位取件码' });
      return;
    }
    const base = this.getBaseUrl();
    this.setData({ isSubmitting: true, pickupResult: '正在验证…' });
    wx.request({
      url: `${base}/api/pickup`,
      method: 'POST',
      header: { 'Content-Type': 'application/json' },
      data: { sample_code: sampleCode, pickup_code: pickupCode },
      success: (res) => {
        if (res.statusCode === 200 && res.data.status === 'pickup_requested') {
          wx.showModal({
            title: '✅ 验证成功',
            content: '开锁命令已发送给 NUC。请取出样品并将箱门关好，系统检测锁闭后完成任务。',
            showCancel: false,
            confirmText: '好的'
          });
          this.refresh();
          this.setData({ pickupResult: '✅ 验证成功，等待小车开锁' });
        } else {
          this.setData({ pickupResult: `❌ ${this.getErrorMessage(res, '验证失败')}` });
        }
      },
      fail: () => {
        this.setData({ pickupResult: '❌ 无法连接云端' });
      },
      complete: () => this.setData({ isSubmitting: false })
    });
  },

  // 输入绑定
  setSample(e) { this.setData({ sample: e.detail.value }); },
  setTemp(e) { this.setData({ temp: e.detail.value }); },
  setSenderId(e) { this.setData({ senderId: e.detail.value }); },
  setSampleCode(e) { this.setData({ sampleCode: e.detail.value.toUpperCase() }); },
  setPickupCode(e) { this.setData({ pickupCode: e.detail.value }); },
  setOrigin(e) {
    this.setData({ origin: e.detail.value });
  },
  setTarget(e) {
    this.setData({ target: e.detail.value });
  },
  goBack() { wx.navigateBack(); }
});
