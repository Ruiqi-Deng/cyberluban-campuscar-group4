Page({
  data: {
    robotLocation: '加载中...',
    temperature: '--',
    humidity: '--',
    battery: '--',
    updateTime: ''
  },

  onLoad() {
    this.refreshStatus();
    this.statusTimer = setInterval(() => this.refreshStatus(), 3000);
  },

  onUnload() {
    if (this.statusTimer) clearInterval(this.statusTimer);
  },

  refreshStatus() {
    const baseUrl = getApp().globalData.apiBase;
    wx.request({
      url: `${baseUrl}/api/robot/status`,
      success: (res) => {
        if (res.statusCode === 200 && res.data) {
          const telemetry = res.data.telemetry || {};
          const latestTask = res.data.latest_task;
          const now = new Date();
          const timeStr = now.toLocaleTimeString();
          this.setData({
            robotLocation: latestTask ? latestTask.status_message : '🟢 暂无任务，等待寄件',
            temperature: telemetry.temperature ?? '--',
            humidity: telemetry.humidity ?? '--',
            battery: telemetry.battery ?? '--',
            updateTime: timeStr
          });
        }
      },
      fail: () => {
        this.setData({
          robotLocation: '⚠️ 无法连接后端',
          updateTime: new Date().toLocaleTimeString()
        });
      }
    });
  },

  goToSend() {
    wx.navigateTo({
      url: '/pages/work/work?mode=send'
    });
  },

  goToPickup() {
    wx.navigateTo({
      url: '/pages/work/work?mode=pickup'
    });
  }
});
