import { useQuery } from '@tanstack/react-query';
import { Row, Col, Card, Statistic, Table, Spin, Typography, Tag } from 'antd';
import {
  FundOutlined,
  RiseOutlined,
  FallOutlined,
  PieChartOutlined,
} from '@ant-design/icons';
import { fetchFunds } from '../../api/funds';
import { STRATEGY_LABELS, FUND_STATUS_LABELS } from '../../types';
import type { Fund } from '../../types';

const { Title } = Typography;

export default function Dashboard() {
  const { data: fundsData, isLoading } = useQuery({
    queryKey: ['funds', { page: 1, page_size: 100 }],
    queryFn: () => fetchFunds({ page: 1, page_size: 100 }),
  });

  const funds = fundsData?.data || [];
  const activeFunds = funds.filter((f) => f.status === 'active');
  const totalAum = funds.reduce((sum, f) => sum + (f.aum || 0), 0);

  // Strategy distribution
  const strategyCounts: Record<string, number> = {};
  funds.forEach((f) => {
    strategyCounts[f.strategy_type] = (strategyCounts[f.strategy_type] || 0) + 1;
  });

  const columns = [
    { title: '排名', key: 'rank', width: 60, render: (_: any, __: Fund, i: number) => i + 1 },
    { title: '基金名称', dataIndex: 'name', key: 'name' },
    { title: '策略', dataIndex: 'strategy_type', key: 'strategy', render: (s: string) => <Tag>{STRATEGY_LABELS[s] || s}</Tag> },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color={s === 'active' ? 'green' : 'default'}>{FUND_STATUS_LABELS[s] || s}</Tag> },
    { title: '规模(万元)', dataIndex: 'aum', key: 'aum', render: (v: number) => v ? v.toLocaleString() : '-' },
  ];

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  return (
    <div>
      <Title level={4}>仪表盘</Title>
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic title="基金总数" value={funds.length} prefix={<FundOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic title="运行中" value={activeFunds.length} prefix={<RiseOutlined />} valueStyle={{ color: '#3f8600' }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic title="已清盘" value={funds.filter((f) => f.status === 'liquidated').length} prefix={<FallOutlined />} valueStyle={{ color: '#cf1322' }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic title="总规模(万元)" value={totalAum.toLocaleString()} prefix={<PieChartOutlined />} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={16}>
          <Card title="基金列表">
            <Table
              dataSource={funds.slice(0, 10)}
              columns={columns}
              rowKey="id"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="策略分布">
            {Object.entries(strategyCounts).map(([key, count]) => (
              <div key={key} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <Tag>{STRATEGY_LABELS[key] || key}</Tag>
                <span>{count} 只</span>
              </div>
            ))}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
