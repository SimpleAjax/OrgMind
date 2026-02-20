/**
 * DataTable Component Tests
 */
import { render, screen, fireEvent } from '@/lib/test-utils';
import { DataTable } from '@/components/data-table/data-table';
import { ColumnDef } from '@tanstack/react-table';

interface TestData {
  id: string;
  name: string;
  status: string;
}

const testData: TestData[] = [
  { id: '1', name: 'Item 1', status: 'active' },
  { id: '2', name: 'Item 2', status: 'inactive' },
  { id: '3', name: 'Item 3', status: 'active' },
];

const columns: ColumnDef<TestData>[] = [
  {
    accessorKey: 'id',
    header: 'ID',
  },
  {
    accessorKey: 'name',
    header: 'Name',
  },
  {
    accessorKey: 'status',
    header: 'Status',
  },
];

describe('DataTable', () => {
  it('renders with data', () => {
    render(
      <DataTable
        columns={columns}
        data={testData}
      />
    );

    expect(screen.getByText('Item 1')).toBeInTheDocument();
    expect(screen.getByText('Item 2')).toBeInTheDocument();
    expect(screen.getByText('Item 3')).toBeInTheDocument();
  });

  it('renders loading state', () => {
    render(
      <DataTable
        columns={columns}
        data={[]}
        loading={true}
      />
    );

    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
  });

  it('renders empty state', () => {
    render(
      <DataTable
        columns={columns}
        data={[]}
      />
    );

    expect(screen.getByText('No results.')).toBeInTheDocument();
  });

  it('calls onRowClick when row is clicked', () => {
    const handleRowClick = jest.fn();

    render(
      <DataTable
        columns={columns}
        data={testData}
        onRowClick={handleRowClick}
      />
    );

    const row = screen.getByText('Item 1').closest('tr');
    if (row) {
      fireEvent.click(row);
    }

    expect(handleRowClick).toHaveBeenCalledWith(testData[0]);
  });

  it('filters data based on search', () => {
    render(
      <DataTable
        columns={columns}
        data={testData}
        searchable={true}
      />
    );

    const searchInput = screen.getByPlaceholderText('Search...');
    fireEvent.change(searchInput, { target: { value: 'Item 1' } });

    expect(screen.getByText('Item 1')).toBeInTheDocument();
    expect(screen.queryByText('Item 2')).not.toBeInTheDocument();
  });

  it('renders with custom search placeholder', () => {
    render(
      <DataTable
        columns={columns}
        data={testData}
        searchable={true}
        searchPlaceholder="Custom placeholder..."
      />
    );

    expect(screen.getByPlaceholderText('Custom placeholder...')).toBeInTheDocument();
  });
});
