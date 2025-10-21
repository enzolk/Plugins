import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

ApplicationWindow {
    id: root
    width: 1280
    height: 720
    visible: true
    title: qsTr("ClinicPortable")

    property string currentView: "dashboard"

    readonly property var viewMap: ({
        "dashboard": Qt.resolvedUrl("Dashboard.qml"),
        "patients": Qt.resolvedUrl("Patients.qml"),
        "appointments": Qt.resolvedUrl("Appointments.qml"),
        "consultations": Qt.resolvedUrl("Consultations.qml"),
        "invoices": Qt.resolvedUrl("Invoices.qml"),
        "reports": Qt.resolvedUrl("Reports.qml"),
        "settings": Qt.resolvedUrl("Settings.qml"),
        "backups": Qt.resolvedUrl("Backups.qml"),
    })

    header: ToolBar {
        contentHeight: 40
        RowLayout {
            anchors.fill: parent
            spacing: 12

            Label {
                text: qsTr("ClinicPortable")
                font.bold: true
                font.pointSize: 16
                Layout.alignment: Qt.AlignVCenter
            }

            Label {
                Layout.fillWidth: true
                text: qsTr("Tableau de bord - %1").arg(currentView)
                opacity: 0.7
            }

            Button {
                text: qsTr("Verrouiller")
                onClicked: lockDialog.open()
            }
        }
    }

    Drawer {
        id: drawer
        width: 220
        edge: Qt.LeftEdge
        modal: false
        contentItem: ListView {
            id: navList
            model: [
                { label: qsTr("Tableau de bord"), view: "dashboard" },
                { label: qsTr("Patients"), view: "patients" },
                { label: qsTr("Agenda"), view: "appointments" },
                { label: qsTr("Consultations"), view: "consultations" },
                { label: qsTr("Factures"), view: "invoices" },
                { label: qsTr("Rapports"), view: "reports" },
                { label: qsTr("Paramètres"), view: "settings" },
                { label: qsTr("Sauvegardes"), view: "backups" },
            ]
            delegate: ItemDelegate {
                text: modelData.label
                width: parent.width
                highlighted: modelData.view === root.currentView
                onClicked: {
                    root.currentView = modelData.view
                    drawer.close()
                }
            }
        }
    }

    Shortcut {
        sequences: [ StandardKey.Open ]
        onActivated: drawer.open()
    }

    Loader {
        id: viewLoader
        anchors.fill: parent
        anchors.margins: 12
        source: root.viewMap[root.currentView]
    }

    LoginDialog {
        id: loginDialog
        anchors.centerIn: Overlay.overlay
        visible: true
    }

    Dialog {
        id: lockDialog
        title: qsTr("Verrouillage rapide")
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: {
            // TODO: hook to auth manager
        }
        contentItem: ColumnLayout {
            spacing: 12
            Label {
                text: qsTr("Le verrouillage masquera les données sensibles jusqu'à reconnexion.")
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }
    }
}
