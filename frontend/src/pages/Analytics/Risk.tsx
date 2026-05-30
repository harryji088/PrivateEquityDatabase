import { Typography, Card } from 'antd';

export default function RiskAnalytics() {
  return (
    <div>
      <Typography.Title level={4}>风险分析</Typography.Title>
      <Card><p>VaR、相关性热力图、最大回撤分析等功能将在 Phase 2 实现</p></Card>
    </div>
  );
}
