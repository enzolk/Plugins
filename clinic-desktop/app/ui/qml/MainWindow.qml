import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Controls.Material 2.15
import QtQuick.Layouts 1.15

ApplicationWindow {
    id: root
    visible: true
    width: 1200
    height: 720
    title: qsTr("Clinic Desktop")

    Material.theme: Material.Light
    Material.accent: "#1e88e5"

    header: ToolBar {
        RowLayout {
            anchors.fill: parent
            spacing: 12
            ToolButton {
                icon.name: "menu"
                onClicked: drawer.open()
            }
            Label {
                text: qsTr("Clinic Desktop")
                font.pixelSize: 20
                Layout.fillWidth: true
            }
            Switch {
                id: themeSwitch
                text: checked ? qsTr("Sombre") : qsTr("Clair")
                onToggled: Material.theme = checked ? Material.Dark : Material.Light
            }
        }
    }

    Drawer {
        id: drawer
        width: 240
        modal: false
        ListView {
            anchors.fill: parent
            model: [
                qsTr("Tableau de bord"),
                qsTr("Patients"),
                qsTr("RDV"),
                qsTr("Consultations"),
                qsTr("Factures"),
                qsTr("Rapports"),
                qsTr("Paramètres"),
                qsTr("Sauvegardes")
            ]
            delegate: ItemDelegate {
                text: modelData
                width: ListView.view.width
                onClicked: {
                    stackView.currentIndex = index
                    drawer.close()
                }
            }
        }
    }

    StackLayout {
        id: stackView
        anchors.fill: parent
        anchors.margins: 16
        currentIndex: 0

        Dashboard {}
        PatientsView {}
        AppointmentsView {}
        ConsultationsView {}
        InvoicesView {}
        ReportsView {}
        SettingsView {}
        BackupsView {}
    }
}
