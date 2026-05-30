import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Table, Button, Space, Tag, Input, Select, Modal, Form, message, Typography,
} from 'antd';
import { PlusOutlined, SearchOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { fetchFunds, deleteFund, createFund, fetchCompanies, fetchManagers } from '../../api/funds';
import { STRATEGY_LABELS, FUND_STATUS_LABELS } from '../../types';
import type { Fund } from '../../types';

const { Title } = Typography;

export default function FundList() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [strategyFilter, setStrategyFilter] = useState<string | undefined>();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['funds', { page, page_size: 20, search, strategy_type: strategyFilter, status: statusFilter }],
    queryFn: () => fetchFunds({ page, page_size: 20, search, strategy_type: strategyFilter, status: statusFilter }),
  });

  const { data: companiesData } = useQuery({
    queryKey: ['companies', { page_size: 100 }],
    queryFn: () => fetchCompanies({ page_size: 100 }),
  });

  const { data: managersData } = useQuery({
    queryKey: ['managers', { page_size: 100 }],
    queryFn: () => fetchManagers({ page_size: 100 }),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteFund,
    onSuccess: () => {
      message.success('基金已删除');
      queryClient.invalidateQueries({ queryKey: ['funds'] });
    },
  });

  const createMutation = useMutation({
    mutationFn: createFund,
    onSuccess: () => {
      message.success('基金创建成功');
      setIsModalOpen(false);
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ['funds'] });
    },
  });

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name', render: (text: string, record: Fund) => (
      <a onClick={() => navigate(`/funds/${record.id}`)}>{text}</a>
    )},
    { title: '代码', dataIndex: 'code', key: 'code' },
    {
      title: '策略', dataIndex: 'strategy_type', key: 'strategy',
      render: (s: string) => <Tag color="blue">{STRATEGY_LABELS[s] || s}</Tag>,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status',
      render: (s: string) => <Tag color={s === 'active' ? 'green' : s === 'liquidated' ? 'red' : 'orange'}>{FUND_STATUS_LABELS[s] || s}</Tag>,
    },
    { title: '规模(万元)', dataIndex: 'aum', key: 'aum', render: (v: number) => v ? v.toLocaleString() : '-' },
    { title: '所属公司', dataIndex: 'company_name', key: 'company' },
    { title: '基金经理', dataIndex: 'manager_name', key: 'manager' },
    { title: '成立日期', dataIndex: 'inception_date', key: 'inception_date' },
    {
      title: '操作', key: 'actions',
      render: (_: any, record: Fund) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => navigate(`/funds/${record.id}`)}>详情</Button>
          <Button
            type="link" danger icon={<DeleteOutlined />}
            onClick={() => {
              Modal.confirm({
                title: '确认删除',
                content: `确定要删除基金"${record.name}"吗？`,
                onOk: () => deleteMutation.mutate(record.id),
              });
            }}
          >删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>基金列表</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setIsModalOpen(true)}>新建基金</Button>
      </div>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索基金名称"
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          style={{ width: 250 }}
        />
        <Select
          placeholder="策略类型"
          allowClear
          style={{ width: 150 }}
          value={strategyFilter}
          onChange={(v) => { setStrategyFilter(v); setPage(1); }}
          options={Object.entries(STRATEGY_LABELS).map(([k, v]) => ({ value: k, label: v }))}
        />
        <Select
          placeholder="运行状态"
          allowClear
          style={{ width: 150 }}
          value={statusFilter}
          onChange={(v) => { setStatusFilter(v); setPage(1); }}
          options={Object.entries(FUND_STATUS_LABELS).map(([k, v]) => ({ value: k, label: v }))}
        />
      </Space>

      <Table
        dataSource={data?.data || []}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: page,
          pageSize: 20,
          total: data?.total || 0,
          onChange: setPage,
          showTotal: (total) => `共 ${total} 只基金`,
        }}
      />

      <Modal
        title="新建基金"
        open={isModalOpen}
        onOk={() => form.submit()}
        onCancel={() => setIsModalOpen(false)}
        width={640}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => createMutation.mutate(values)}
          initialValues={{ status: 'active', lockup_period_months: 0 }}
        >
          <Form.Item name="name" label="基金名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="code" label="基金代码">
            <Input />
          </Form.Item>
          <Form.Item name="company_id" label="所属公司" rules={[{ required: true }]}>
            <Select options={(companiesData?.data || []).map((c: any) => ({ value: c.id, label: c.name }))} />
          </Form.Item>
          <Form.Item name="manager_id" label="基金经理">
            <Select options={(managersData?.data || []).map((m: any) => ({ value: m.id, label: m.name }))} />
          </Form.Item>
          <Form.Item name="strategy_type" label="策略类型" rules={[{ required: true }]}>
            <Select options={Object.entries(STRATEGY_LABELS).map(([k, v]) => ({ value: k, label: v }))} />
          </Form.Item>
          <Form.Item name="inception_date" label="成立日期" rules={[{ required: true }]}>
            <Input placeholder="YYYY-MM-DD" />
          </Form.Item>
          <Form.Item name="aum" label="规模(万元)">
            <Input type="number" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
