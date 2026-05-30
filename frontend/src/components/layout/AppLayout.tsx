import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Typography, ConfigProvider, theme } from 'antd';
import {
  DashboardOutlined,
  FundOutlined,
  LineChartOutlined,
  BarChartOutlined,
  SwapOutlined,
  ImportOutlined,
  FileTextOutlined,
} from '@ant-design/icons';

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/funds', icon: <FundOutlined />, label: '基金列表' },
  { key: '/nav', icon: <LineChartOutlined />, label: '净值管理' },
  {
    key: '/analytics',
    icon: <BarChartOutlined />,
    label: '分析',
    children: [
      { key: '/analytics/performance', label: '绩效分析' },
      { key: '/analytics/risk', label: '风险分析' },
    ],
  },
  { key: '/comparison', icon: <SwapOutlined />, label: '基金对比' },
  { key: '/import-export', icon: <ImportOutlined />, label: '导入导出' },
  { key: '/reports', icon: <FileTextOutlined />, label: '报告' },
];

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  // Determine selected key
  const selectedKey = location.pathname.startsWith('/analytics')
    ? location.pathname.split('/').slice(0, 3).join('/')
    : location.pathname;
  const openKeys = location.pathname.startsWith('/analytics') ? ['/analytics'] : [];

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#1677ff',
          borderRadius: 6,
        },
      }}
    >
      <Layout style={{ minHeight: '100vh' }}>
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          style={{ borderRight: '1px solid #f0f0f0' }}
        >
          <div
            style={{
              height: 64,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderBottom: '1px solid #f0f0f0',
            }}
          >
            <Typography.Title
              level={4}
              style={{ color: '#1677ff', margin: 0, whiteSpace: 'nowrap' }}
            >
              {collapsed ? 'CC' : 'CC 基金平台'}
            </Typography.Title>
          </div>
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            defaultOpenKeys={openKeys}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
            style={{ borderRight: 0 }}
          />
        </Sider>
        <Layout>
          <Header
            style={{
              padding: '0 24px',
              background: '#fff',
              borderBottom: '1px solid #f0f0f0',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <Typography.Title level={5} style={{ margin: 0 }}>
              量化私募业绩数据库
            </Typography.Title>
          </Header>
          <Content style={{ margin: 16, padding: 24, background: '#fff', borderRadius: 8 }}>
            <Outlet />
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  );
}
