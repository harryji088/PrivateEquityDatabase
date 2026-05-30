import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Table, Select, Upload, Button, Space, message, Typography, Card, Modal,
} from 'antd';
import { UploadOutlined, DownloadOutlined, PlusOutlined } from '@ant-design/icons';
import { fetchFunds, fetchNavData, importNavCsv } from '../../api/funds';
import type { Fund } from '../../types';

const { Title } = Typography;

export default function NavManagement() {
  const queryClient = useQueryClient();
  const [selectedFundId, setSelectedFundId] = useState<string | null>(null);
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  const { data: fundsData } = useQuery({
    queryKey: ['funds', { page_size: 200 }],
    queryFn: () => fetchFunds({ page_size: 200 }),
  });

  const { data: navData, isLoading } = useQuery({
    queryKey: ['nav', selectedFundId, { page_size: 200 }],
    queryFn: () => fetchNavData(selectedFundId!, { page_size: 200 }),
    enabled: !!selectedFundId,
  });

  const importMutation = useMutation({
    mutationFn: ({ fundId, file }: { fundId: string; file: File }) => importNavCsv(fundId, file),
    onSuccess: (data: any) => {
      message.success(data?.message || '导入完成');
      setIsImportOpen(false);
      setUploadFile(null);
      queryClient.invalidateQueries({ queryKey: ['nav'] });
    },
    onError: () => message.error('导入失败'),
  });

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
      <Title level={4}>净值数据管理</Title>

      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select
            placeholder="选择基金"
            style={{ width: 300 }}
            showSearch
            optionFilterProp="label"
            value={selectedFundId}
            onChange={setSelectedFundId}
            options={(fundsData?.data || []).map((f: Fund) => ({
              value: f.id,
              label: `${f.name} (${f.code || 'N/A'})`,
            }))}
          />
          <Button
            icon={<PlusOutlined />}
            onClick={() => setIsImportOpen(true)}
            disabled={!selectedFundId}
          >
            导入净值
          </Button>
          <Button
            icon={<DownloadOutlined />}
            href={`/api/v1/import/template/nav`}
          >
            下载模板
          </Button>
        </Space>
      </Card>

      {selectedFundId && (
        <Table
          dataSource={navData?.data || []}
          columns={navColumns}
          rowKey="id"
          loading={isLoading}
          pagination={{ pageSize: 50, showTotal: (t) => `共 ${t} 条记录` }}
          size="small"
        />
      )}

      {!selectedFundId && (
        <Card><p>请先选择一支基金以查看净值数据</p></Card>
      )}

      <Modal
        title="导入净值数据"
        open={isImportOpen}
        onOk={() => {
          if (uploadFile && selectedFundId) {
            importMutation.mutate({ fundId: selectedFundId, file: uploadFile });
          }
        }}
        onCancel={() => { setIsImportOpen(false); setUploadFile(null); }}
        confirmLoading={importMutation.isPending}
      >
        <Upload
          beforeUpload={(file) => {
            setUploadFile(file);
            return false;
          }}
          maxCount={1}
          accept=".csv,.xlsx"
        >
          <Button icon={<UploadOutlined />}>选择文件 (.csv 或 .xlsx)</Button>
        </Upload>
        <p style={{ marginTop: 8, color: '#888' }}>列格式: date, nav, cumulative_nav</p>
      </Modal>
    </div>
  );
}
