import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Descriptions, Tag, Card, Table, Spin, Button, Typography, Tabs } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { fetchFund, fetchNavData } from '../../api/funds';
import { STRATEGY_LABELS, FUND_STATUS_LABELS } from '../../types';

const { Title } = Typography;

export default function FundDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: fund, isLoading } = useQuery({
    queryKey: ['fund', id],
    queryFn: () => fetchFund(id!),
    enabled: !!id,
  });

  const { data: navData, isLoading: navLoading } = useQuery({
    queryKey: ['nav', id, { page_size: 500 }],
    queryFn: () => fetchNavData(id!, { page_size: 500 }),
    enabled: !!id,
  });

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!fund) return <div>基金未找到</div>;

  const navColumns = [
    { title: '日期', dataIndex: 'date', key: 'date' },
    { title: '单位净值', dataIndex: 'nav', key: 'nav', render: (v: number) => v?.toFixed(4) },
    { title: '累计净值', dataIndex: 'cumulative_nav', key: 'cumulative_nav', render: (v: number) => v?.toFixed(4) },
    {
      title: '日收益率', dataIndex: 'daily_return', key: 'daily_return',
      render: (v: number | null) => {
        if (v === null || v === undefined) return '-';
        const pct = (v * 100).toFixed(4);
        return <span style={{ color: v >= 0 ? '#3f8600' : '#cf1322' }}>{pct}%</span>;
      },
    },
  ];

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/funds')} style={{ marginBottom: 16 }}>
        返回列表
      </Button>
      <Title level={4}>{fund.name}</Title>

      <Card style={{ marginBottom: 16 }}>
        <Descriptions column={{ xs: 1, sm: 2, md: 3 }} bordered size="small">
          <Descriptions.Item label="基金代码">{fund.code || '-'}</Descriptions.Item>
          <Descriptions.Item label="策略类型"><Tag color="blue">{STRATEGY_LABELS[fund.strategy_type] || fund.strategy_type}</Tag></Descriptions.Item>
          <Descriptions.Item label="运行状态"><Tag color={fund.status === 'active' ? 'green' : 'red'}>{FUND_STATUS_LABELS[fund.status]}</Tag></Descriptions.Item>
          <Descriptions.Item label="所属公司">{fund.company_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="基金经理">{fund.manager_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="成立日期">{fund.inception_date}</Descriptions.Item>
          <Descriptions.Item label="基金规模(万元)">{fund.aum ? fund.aum.toLocaleString() : '-'}</Descriptions.Item>
          <Descriptions.Item label="管理费率">{fund.management_fee_rate ? `${(fund.management_fee_rate * 100).toFixed(2)}%` : '-'}</Descriptions.Item>
          <Descriptions.Item label="业绩报酬率">{fund.performance_fee_rate ? `${(fund.performance_fee_rate * 100).toFixed(2)}%` : '-'}</Descriptions.Item>
          <Descriptions.Item label="锁定期(月)">{fund.lockup_period_months || 0}</Descriptions.Item>
          <Descriptions.Item label="最低认购(元)">{fund.min_subscription_amount ? fund.min_subscription_amount.toLocaleString() : '-'}</Descriptions.Item>
          <Descriptions.Item label="申购频率">{fund.subscription_frequency || '-'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Tabs defaultActiveKey="nav">
        <Tabs.TabPane tab="净值数据" key="nav">
          <Table
            dataSource={navData?.data || []}
            columns={navColumns}
            rowKey="id"
            loading={navLoading}
            pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条净值记录` }}
            size="small"
          />
        </Tabs.TabPane>
        <Tabs.TabPane tab="绩效指标" key="metrics">
          <Card><p>绩效指标分析将在 Phase 2 实现</p></Card>
        </Tabs.TabPane>
        <Tabs.TabPane tab="净值曲线" key="chart">
          <Card><p>净值曲线图将在 Phase 2 实现</p></Card>
        </Tabs.TabPane>
      </Tabs>
    </div>
  );
}
