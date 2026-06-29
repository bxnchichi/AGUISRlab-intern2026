// CfsView.cpp : コンソール アプリケーション用のエントリ ポイントの定義
//

#include "stdafx.h"

#include <conio.h>
#include "CfsUsb.h"
#include <winsock2.h>
#include <windows.h>
#include <ws2tcpip.h>
#include <iostream>
#include <thread>
#include <chrono>
#include <time.h>

// Winsockライブラリをリンク
#pragma comment(lib, "Ws2_32.lib")

typedef void (CALLBACK *FUNC_Initialize)();
typedef void (CALLBACK *FUNC_Finalize)();
typedef bool (CALLBACK *FUNC_PortOpen)(int);
typedef void (CALLBACK *FUNC_PortClose)(int);
typedef bool (CALLBACK *FUNC_SetSerialMode)(int,bool);
typedef bool (CALLBACK* FUNC_GetSerialData)(int,double *,char *);
typedef bool (CALLBACK* FUNC_GetLatestData)(int,double *,char *);
typedef bool (CALLBACK *FUNC_GetSensorLimit)(int,double *);
typedef bool (CALLBACK* FUNC_GetSensorInfo)( int, char *);

int _tmain(int argc, _TCHAR* argv[])
{
	HMODULE hDll;
	long cnt;
	int portNo = 9;
	char SerialNo[9];
	char Status;
	double Limit[6];
	double Data[6];
	double Fx,Fy,Fz,Mx,My,Mz;
	double sensor_data[7] = { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 };

	FUNC_Initialize Initialize;
	FUNC_Finalize Finalize;
	FUNC_PortOpen PortOpen;
	FUNC_PortClose PortClose;
	FUNC_SetSerialMode SetSerialMode;
	FUNC_GetSerialData GetSerialData;
	FUNC_GetLatestData GetLatestData;
	FUNC_GetSensorLimit GetSensorLimit;
	FUNC_GetSensorInfo GetSensorInfo;

	// Winsockの初期化
	WSADATA wsaData;
	if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
		std::cerr << "WSAStartup failed" << std::endl;
		return -1;
	}

	// ソケットの作成
	SOCKET sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
	if (sock == INVALID_SOCKET) {
		std::cerr << "Socket creation failed" << std::endl;
		WSACleanup();
		return -1;
	}

	// サーバーのアドレス設定
	sockaddr_in server_addr;
	memset(&server_addr, 0, sizeof(server_addr));
	server_addr.sin_family = AF_INET;
	server_addr.sin_port = htons(12345); // ポート番号
	inet_pton(AF_INET, "127.0.0.1", &server_addr.sin_addr); // localhost


	// ＤＬＬのロード
	hDll = LoadLibrary("CfsUsb.dll");

	// ＤＬＬが正常にロードできた
	if (hDll != NULL) 
	{
		// 関数アドレスの取得
		Initialize		= (FUNC_Initialize    )GetProcAddress(hDll,"Initialize");		// ＤＬＬの初期化処理
		Finalize		= (FUNC_Finalize      )GetProcAddress(hDll,"Finalize");			// ＤＬＬの終了処理
		PortOpen		= (FUNC_PortOpen      )GetProcAddress(hDll,"PortOpen");			// ポートオープン
		PortClose		= (FUNC_PortClose     )GetProcAddress(hDll,"PortClose");		// ポートクローズ
		SetSerialMode	= (FUNC_SetSerialMode )GetProcAddress(hDll,"SetSerialMode");	// データの連続読込の開始/停止
		GetSerialData	= (FUNC_GetSerialData )GetProcAddress(hDll,"GetSerialData");	// 連続データ読込み
		GetLatestData	= (FUNC_GetLatestData )GetProcAddress(hDll,"GetLatestData");	// 最新データ読込
		GetSensorLimit	= (FUNC_GetSensorLimit)GetProcAddress(hDll,"GetSensorLimit");	// センサ定格確認
		GetSensorInfo	= (FUNC_GetSensorInfo )GetProcAddress(hDll,"GetSensorInfo");	// シリアルNo取得

		// ＤＬＬの初期化処理
		Initialize();
		
		// ポートオープン
		if(PortOpen(portNo) == true)
		{
			// センサ定格確認
			if(GetSensorLimit(portNo, Limit) == false)
			{
				printf("センサ定格確認ができません。");
			}
			// シリアルNo確認
			if(GetSensorInfo(portNo ,SerialNo) == false)
			{
				printf("シリアルNoが取得できません。");
			}
			/****************************/
			/* ハンドシェイクによる読込 */
			/****************************/
			// 最新データ読込
			// ※センサからは定格を10000としてデータが出力されてくる
			if(GetLatestData(portNo, Data, &Status) == true)
			{
			
						Fx = Limit[0] / 10000 * Data[0];								// Fxの値
						Fy = Limit[1] / 10000 * Data[1];								// Fyの値
						Fz = Limit[2] / 10000 * Data[2];								// Fzの値
						Mx = Limit[3] / 10000 * Data[3];								// Mxの値
						My = Limit[4] / 10000 * Data[4];								// Myの値
						Mz = Limit[5] / 10000 * Data[5];								// Mzの値
					

						printf("GetLastData\n");
					printf("Fx:%.3f Fy:%.3f Fz:%.3f Mx:%.3f My:%.3f Mz:%.2f\r", Fx, Fy, Fz, Mx, My, Mz);
			}
			else
			{
				printf("最新データ取得に失敗しました。");
			}

			/************/
			/* 連続読込 */
			/************/
			// 連続データ読込モードに移行
			
			auto current_time = std::chrono::steady_clock::now();
			
			if(SetSerialMode(portNo,true) == true)
			{
				// 10000回連続読込
				cnt =0;
				printf("GetSerialData\n");


				while(cnt<50000)
				{
					static auto start_time = std::chrono::steady_clock::now();
					auto pre_time = std::chrono::steady_clock::now();


					// データ取得
					if(GetSerialData(portNo, Data, &Status) == true)
					{
						Fx = sensor_data[1] = Limit[0] / 10000 *	Data[0];						// Fxの値
						Fy = sensor_data[2] = Limit[1] / 10000 *	Data[1];						// Fyの値
						Fz = sensor_data[3] = Limit[2] / 10000 *	Data[2];						// Fzの値
						Mx = sensor_data[4] = Limit[3] / 10000 *	Data[3];						// Mxの値
						My = sensor_data[5] = Limit[4] / 10000 *	Data[4];						// Myの値
						Mz = sensor_data[6] = Limit[5] / 10000 *	Data[5];						// Mzの値

						cnt++;
						
						current_time = std::chrono::steady_clock::now();
						auto elapsed_time = std::chrono::duration_cast<std::chrono::microseconds>(current_time - start_time).count();
						auto one_looptime = std::chrono::duration_cast<std::chrono::microseconds>(current_time - pre_time).count();

						printf("time: %lld looptime: %lld cnt: %d Fx:%.3f Fy:%.3f Fz:%.3f Mx:%.3f My:%.3f Mz:%.3f             \r",elapsed_time,one_looptime,cnt,Fx,Fy,Fz,Mx,My,Mz);




						int sent = sendto(sock, (char*)sensor_data, sizeof(sensor_data), 0,
							(sockaddr*)&server_addr, sizeof(server_addr));
						if (sent == SOCKET_ERROR) {
							std::cerr << "Failed to send data" << std::endl;
							closesocket(sock);
							WSACleanup();
							return -1;
						}

						//std::cout << "Sent data: ";
						//for (float value : sensor_data) {
						//	std::cout << value << " ";
						//}
						//std::cout << std::endl;

						//std::this_thread::sleep_for(std::chrono::microseconds(10000 - one_looptime));
						//std::this_thread::sleep_for(std::chrono::microseconds(15000));
						//std::chrono::microseconds duration(10000);  // 10,000マイクロ秒（0.01秒）
						//std::this_thread::sleep_for(duration);


						
						
					}

				}

			

				// 連続データ読込モードを停止
				if(SetSerialMode(portNo, false) == false)
				{
					printf("連続読込モードを停止できません。");
				}
			}
			else
			{
				printf("連続読込モードに移行できません。");
			}

			// ポートクローズ
			PortClose(portNo);
			// ソケットを閉じる
			closesocket(sock);
			WSACleanup();
			return 0;
		}
		else
		{
			printf("回線がオープンできません。");
		}

		// ＤＬＬの終了処理
		Finalize();

		// ＤＬＬの解放
		FreeLibrary(hDll);

		printf("\n完了");
	}
	// ＤＬＬのロードに失敗
	else
	{
		printf("DLLのロードに失敗しました。");
	}

	printf("\n何かキーを押してください。");
	while( !_kbhit() ) {
	}

	return 0;
}

