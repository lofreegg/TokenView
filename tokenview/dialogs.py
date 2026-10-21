from System.Drawing import Size, Point, Color, Font, FontStyle
from System.Windows.Forms import Form, FormBorderStyle, FormStartPosition, Label, TextBox, Button, DialogResult, MessageBox, MessageBoxButtons, MessageBoxIcon


def add_account(owner, product, account_count):
    dialog = Form()
    dialog.Text = '添加 Key' if product == 'deepseek' else '添加账号'
    dialog.ClientSize = Size(400, 258 if product == 'deepseek' else 210)
    dialog.FormBorderStyle = FormBorderStyle.FixedDialog
    dialog.StartPosition = FormStartPosition.CenterParent
    dialog.MaximizeBox = False
    dialog.MinimizeBox = False
    dialog.ShowInTaskbar = False
    dialog.BackColor = Color.White
    dialog.Font = Font('Microsoft YaHei UI', 10.0)
    def label(text, y):
        control = Label()
        control.Text = text
        control.Location = Point(22, y)
        control.Size = Size(356, 26)
        dialog.Controls.Add(control)
    label('账号名称（仅本机显示）', 18)
    name = TextBox()
    name.Location = Point(22, 48)
    name.Size = Size(356, 28)
    name.MaxLength = 50
    name.Text = ''
    dialog.Controls.Add(name)
    secret = None
    if product == 'deepseek':
        label('API Key（Windows 本机加密保存）', 90)
        secret = TextBox()
        secret.Location = Point(22, 121)
        secret.Size = Size(356, 28)
        secret.UseSystemPasswordChar = True
        dialog.Controls.Add(secret)
    else:
        note = '会打开官方登录页面，每个账号独立授权。' if product == 'codex' else '打开 Google 登录，选择要新增的账号。\n独立加密保存，不切换 MyAgents 当前账号。'
        label(note, 91)
        dialog.Controls[dialog.Controls.Count - 1].Size = Size(356, 52)
    confirm = Button()
    confirm.Text = '保存' if product == 'deepseek' else '登录授权'
    confirm.Location = Point(240, dialog.ClientSize.Height - 52)
    confirm.Size = Size(138, 32)
    cancel = Button()
    cancel.Text = '取消'
    cancel.Location = Point(148, dialog.ClientSize.Height - 52)
    cancel.Size = Size(82, 32)
    cancel.DialogResult = DialogResult.Cancel
    result = []
    def accept(sender, event):
        if not name.Text.strip() or (secret is not None and not secret.Text.strip()):
            MessageBox.Show(dialog, '请填写名称和 Key' if secret is not None else '请填写账号名称')
            return
        result.append((str(name.Text).strip(), str(secret.Text).strip() if secret is not None else None))
        dialog.DialogResult = DialogResult.OK
        dialog.Close()
    confirm.Click += accept
    dialog.Controls.Add(confirm)
    dialog.Controls.Add(cancel)
    dialog.AcceptButton = confirm
    dialog.CancelButton = cancel
    dialog.ShowDialog(owner)
    dialog.Dispose()
    return result[0] if result else None
