"""Write styled operation-report worksheets without retaining all workbook cells or rows."""

import math
import warnings


def streamed_sheet(workbook,name,title,context,headers,rows,widths,table_name,count,number_formats=None):
    """Stream one table while preserving the established headings, filters and cell styling."""
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Alignment,Font,PatternFill
    from openpyxl.worksheet.table import Table,TableStyleInfo
    from openpyxl.utils import get_column_letter
    sheet=workbook.create_sheet(name);sheet.sheet_view.showGridLines=False;sheet.freeze_panes='A6'
    for column,width in enumerate(widths,1):sheet.column_dimensions[get_column_letter(column)].width=width
    font=Font(name='Arial',size=11,color='243247');alignment=Alignment(vertical='center',wrap_text=True)
    heading=Font(name='Arial',size=11,bold=True,color='FFFFFF');fill=PatternFill('solid',fgColor='234568')
    def append(values,row_number,header=False):
        cells=[]
        for column,value in enumerate(values,1):
            cell=WriteOnlyCell(sheet,value=value);cell.font=heading if header else font;cell.alignment=alignment
            if isinstance(value,str):cell.data_type='s'
            if header:
                cell.fill=fill;cell.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
            if row_number==2:cell.font=Font(name='Arial',size=16,bold=True,color='243247')
            if row_number==3:cell.font=Font(name='Arial',size=10,italic=True,color='58677B');cell.alignment=Alignment(wrap_text=False)
            if number_formats and row_number>=6 and column in number_formats:cell.number_format=number_formats[column]
            cells.append(cell)
        sheet.append(cells)
    append([None]*len(headers),1);append([title]+[None]*(len(headers)-1),2)
    append([context]+[None]*(len(headers)-1),3);append([None]*len(headers),4)
    sheet.row_dimensions[5].height=32;append(headers,5,header=True)
    for number,values in enumerate(rows,6):
        lines=max(sum(max(1,math.ceil(len(line)/max(1,widths[i]-2))) for line in str(value or '').split('\n')) for i,value in enumerate(values))
        sheet.row_dimensions[number].height=min(409,max(18,lines*15));append(values,number)
        # The row tag is already serialized by append; avoid a growing dimension dictionary.
        del sheet.row_dimensions[number]
    if not count:append([None]*len(headers),6)
    table=Table(displayName=table_name,ref=f'A5:{get_column_letter(len(headers))}{max(6,5+count)}')
    table._initialise_columns()
    for column,label in zip(table.tableColumns,headers):column.name=label
    table.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showRowStripes=True)
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',message='In write-only mode you must add table columns manually')
        sheet.add_table(table)
