import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Dialog {
    id: invoiceForm
    title: qsTr("Nouvelle facture")
    modal: true
    width: 600
    standardButtons: Dialog.Save | Dialog.Cancel

    contentItem: ColumnLayout {
        spacing: 8
        padding: 12
        ComboBox { Layout.fillWidth: true; model: ["OST", "DRL"] }
        TextField { Layout.fillWidth: true; placeholderText: qsTr("Patient") }
        DatePicker { }
        TableView {
            Layout.fillWidth: true
            Layout.preferredHeight: 200
            model: 3
            TableViewColumn { role: "description"; title: qsTr("Acte") }
            TableViewColumn { role: "qty"; title: qsTr("Qté") }
            TableViewColumn { role: "price"; title: qsTr("Prix HT") }
        }
        TextArea { Layout.fillWidth: true; Layout.preferredHeight: 80; placeholderText: qsTr("Note publique") }
    }
}
